"""
Evaluator for the RAG application with the following metrics:
recall@k (binary relevance) - order unaware
precision@k (binary relevance) - order unaware
nDCG@k (graded relevance) - order aware

All metrics evaluate the retreival part of this (RAG-)application
(i.e: sections creation, embeddings creation, search implementation etc..)

The evaluator can be run as a standalone script or imported as a module.
"""

from dotenv import load_dotenv
load_dotenv()
import json
import math
from dataclasses import dataclass, field
from server.redis_store import RedisStore
from util import get_embedding
import numpy as np
from server import settings
import logging

redis_store = None


def init():
    settings.check_required()   # .. or fail early!
    settings.print_settings_with_defaults()
    global redis_store
    redis_store = RedisStore()
    logging.info('starting evaluator')


def get_query_vector(query: str) -> bytes:
    query_embedding = get_embedding(query)
    return np.array(query_embedding).astype(np.float32).tobytes()


def load_evaluation_dataset() -> list[dict]:
    if settings.lang == "sv":
        print('loading evaluation data set for swedish version')
        with open('./data/evaluation_data_set.json') as eds:
            data = json.load(eds)
            return data
    elif settings.lang == "en":
        print('loading evaluation data set for engligh version')
        with open('./data/evaluation_data_set_en.json') as eds:
            data = json.load(eds)
            return data
    else:
        print(f'language {settings.lang} not supported')
        exit(1)


def recall_k(k: int, data: dict, query_vector: bytes) -> float:
    """
    recall@k (how many of the existing relevant sections are returned among top K?) focus: Coverage
    (a binary relevance metric. order unaware)

    Parameters:
        k (int): number of sections to retrieve
        data (object from evaluation data set): contains query and all_relevant_section_headers

    Returns:
        recall (float): the recall@k score (max is 1.0)
    """
    retrieved_sections = redis_store.search_sections(query_vector, k)
    all_relevant_section_objects = data["relevant_section_headers"]
    all_relevant_section_headers = []
    for o in all_relevant_section_objects:
        all_relevant_section_headers.append(o["title"])

    relevant_sections = [section for _, section in enumerate(retrieved_sections.docs) if section.header in all_relevant_section_headers]
    retreived_relevant = len(relevant_sections)

    if len(all_relevant_section_headers) == 0:  # if no relevant sections...
        return 0

    recall = retreived_relevant / len(all_relevant_section_headers)
    return round(recall, 2)


def precision_k(k: int, data: dict, query_vector: bytes) -> float:
    """
    precision@k (how many sections returned are actually relevant?) focus: Accuracy
    (a binary relevance metric. order unaware)

    Parameters:
        k (int): number of sections to retrieve
        data (object from evaluation data set): contains query and all_relevant_section_headers

    Returns:
        precision (float): the precision@k score (max is 1.0)
    """
    retrieved_sections = redis_store.search_sections(query_vector, k)
    all_relevant_section_objects = data["relevant_section_headers"]
    all_relevant_section_headers = []
    for o in all_relevant_section_objects:
        all_relevant_section_headers.append(o["title"])

    relevant_sections = [section for _, section in enumerate(retrieved_sections.docs) if section.header in all_relevant_section_headers]

    if len(retrieved_sections.docs) == 0:  # if no retrieved sections
        return 0

    precision = len(relevant_sections) / len(retrieved_sections.docs)
    return round(precision, 2)


def calculate_dcg(k: int, data: dict, query_vector: bytes) -> float:
    """
    Calculate DCG for the top-k retrieved sections based on their actual retrieved order.
    (graded relevance metric. order aware)

    Parameters:
        k (int): Number of top sections to evaluate.
        data (dict): Contains the query and relevant section headers with relevance grades.

    Returns:
        float: DCG score for the top-k retrieved sections.
    """
    retrieved_sections = redis_store.search_sections(query_vector, k)

    # Create a mapping of relevance grades for quick lookup
    relevance_map = {item["title"]: item["rel_grade"] for item in data["relevant_section_headers"]}

    # Assign relevance grades to retrieved sections (while preserving order of retrieval)
    dcgs = []
    for i, section in enumerate(retrieved_sections.docs[:k], start=1):  # Rank starts at 1
        rel_grade = relevance_map.get(section.header, 0)  # Default to 0 if not found (not expected in eval set = not relevant at all)
        dcgs.append(rel_grade / math.log2(i + 1))

    return sum(dcgs)


# does not care about the actual retreived sections
# purpose is to get the perfect DCG score for comparison (based on the eval set)
def calculate_idcg(k: int, data: dict) -> float:
    """
    Calculate IDCG for the top-k ideal ranking of sections.
    (based on ideal sorting on rel_grade)

    Parameters:
        k (int): Number of top sections to evaluate.
        data (dict): Contains the query and relevant section headers with relevance grades.

    Returns:
        float: IDCG score for the top-k ideal ranking.
    """
    # Sort sections by relevance grade (descending) to get the ideal order
    sorted_relevant_sections = sorted(data["relevant_section_headers"], key=lambda x: x["rel_grade"], reverse=True)

    # Calculate IDCG using the ideal ranking
    idcgs = []
    for i, section in enumerate(sorted_relevant_sections[:k], start=1):
        idcgs.append(section["rel_grade"] / math.log2(i + 1))

    return sum(idcgs)


def ndcg_k(k: int, data: dict, query_vector: bytes) -> float:
    """
    ndcg@k (Normalized Discounted Cumulative Gain) focus: Quality - via ranking on relvance
    (graded relevance metric. order aware)
    (ndcg = dcg / idcg) idcg = dcg but calculated on the ideal sorting of the sections based on rel_grade

    Parameters:
        k (int): number of sections to retrieve
        data (object from evaluation data set): contains query and all_relevant_section_headers (with rel_grade)

    Returns:
        ndcg (float): the ndcg@k score (max is 1.0)
    """

    dcg = calculate_dcg(3, data, query_vector)
    idcg = calculate_idcg(3, data)
    ndcg = dcg / idcg if idcg > 0 else 0
    return ndcg


@dataclass
class EvaluationResult:
    avg_recall: float = 0.0
    avg_precision: float = 0.0
    avg_ndcg: float = 0.0
    details: list = field(default_factory=list)


def run_eval(k=3):
    init()
    details = []
    result = EvaluationResult()
    dataset = load_evaluation_dataset()
    total_recall = []  # arnold
    total_precision = []
    total_ndcg = []
    for d in dataset:
        query = d["query"]
        query_vector = get_query_vector(query)
        recall = recall_k(k, d, query_vector)
        total_recall.append(recall)
        precision = precision_k(k, d, query_vector)
        total_precision.append(precision)
        ndcg = ndcg_k(k, d, query_vector)
        total_ndcg.append(ndcg)
        details.append({
            "query": d["query"],
            f"recall@{k}": recall,
            f"precision@{k}": precision,
            f"nDCG@{k}": round(ndcg, 2)
        })

    result.details = details
    result.avg_recall = round(sum(total_recall) / len(total_recall), 2)
    result.avg_precision = round(sum(total_precision) / len(total_precision), 2)
    result.avg_ndcg = round(sum(total_ndcg) / len(total_ndcg), 2)
    return result


if __name__ == "__main__":
    results = run_eval()
    print("Details:")
    for d in results.details:
        print(d)

    print(f"Average recall@3: {results.avg_recall}")
    print(f"Average precision@3: {results.avg_precision}")
    print(f"Average nDCG@3: {results.avg_ndcg}")
