from dotenv import load_dotenv
load_dotenv(dotenv_path='../.env')

from unittest.mock import Mock, patch
from evaluator import recall_k, precision_k, ndcg_k
from tests.base_test import BaseTest


class TestHandleQuery(BaseTest):

    def setUp(self):
        super().setUp()
        # Create a mock RedisStore
        self.mock_redis = Mock()
        # Patch evaluator.redis_store to use self.mock_redis
        patcher = patch('evaluator.redis_store', self.mock_redis)
        self.addCleanup(patcher.stop)  # Ensure the patch is removed after the test
        patcher.start()

        # Evaluation dataset
        self.data = [
            {
                "query": "När börjar höstterminen?",
                "relevant_section_headers": [
                    {"title": "2.4 Läsår och terminstider", "rel_grade": 5},
                    {"title": "12.3 Tillfälligt antagningsstopp", "rel_grade": 3},
                    {"title": "13.1 Anmälan till program (programtillfälle)", "rel_grade": 2}
                ]
            },
            {
                "query": "Vad är cellbiologi och vilka sorter studeras på SLU?",
                "relevant_section_headers": [
                    {"title": "Bilaga 3b: Ämnesbeskrivningar för SLU:s huvudområden... sida 4", "rel_grade": 5},
                    {"title": "Bilaga 3b: Ämnesbeskrivningar för SLU:s huvudområden... sida 21", "rel_grade": 3},
                    {"title": "Bilaga 3a: Ämnen vid SLU inom utbildning på grundnivå och avancerad ni... sida 1", "rel_grade": 2}
                ]
            }
        ]

    # recall_k is about Coverage, out of all relevant sections how many are retrieved
    def test_recall_k_returns_67_if_retrieved_2_out_of_3(self):
        # Arrange
        # Mock search_sections in redis_store
        mock_section = Mock()
        mock_section.configure_mock(header="2.4 Läsår och terminstider",
                                    body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.0001)
        # another mock section
        mock_section2 = Mock()
        mock_section2.configure_mock(header="12.3 Tillfälligt antagningsstopp",
                                     body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.1)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section, mock_section2])
        fake_query_vector = [0.1, 0.2, 3.0]

        # Act
        # expecting 3 relevant sections but only 2 are retrieved (should return 0.67)
        r = recall_k(k=3, data=self.data[0], query_vector=fake_query_vector)

        # Assert
        self.assertEqual(r, 0.67)

    # precision_k is about Accuracy, how many of the retrieved sections are actually relevant
    def test_precision_k_returns_50_if_retrieved_2_but_one_not_relevant(self):
        # Arrange
        # Mock search_sections in redis_store
        mock_section = Mock()
        mock_section.configure_mock(header="2.4 Läsår och terminstider",
                                    body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.0001)
        # another mock section
        mock_section2 = Mock()
        mock_section2.configure_mock(header="27.7 Does not exist in eval data set",
                                     body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.1)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section, mock_section2])
        fake_query_vector = [0.1, 0.2, 3.0]

        # Act
        # expecting 2 relevant sections but only 1 out of 2 retrieved  is relevant (should return 0.5)
        r = precision_k(k=3, data=self.data[0], query_vector=fake_query_vector)

        # Assert
        self.assertEqual(r, 0.5)

    # nDCG is about quality via ranking on relevance, how well are the relevant sections ranked
    def test_ndcg_should_detect_non_ideal_ranking_order(self):
        # Arrange
        # Mock search_sections in redis_store
        mock_section = Mock()
        mock_section.configure_mock(header="2.4 Läsår och terminstider",
                                    body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.0001)
        # another mock section
        mock_section2 = Mock()
        mock_section2.configure_mock(header="12.3 Tillfälligt antagningsstopp",
                                     body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.1)

        # a third mock section
        mock_section3 = Mock()
        mock_section3.configure_mock(header="13.1 Anmälan till program (programtillfälle)",
                                     body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=0.2)

        # not returned in the optimal relevance order
        # ideal would be mocked_section, mock_sections_2, mock_section_3
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section3, mock_section2, mock_section])
        fake_query_vector = [0.1, 0.2, 3.0]

        # Act
        # expecting sections retrieved in ideal order but they are not (should return 0.81)
        r = ndcg_k(k=3, data=self.data[0], query_vector=fake_query_vector)
        r = round(r, 2)

        # Explanation why we expect a nDCG score of 0.81:
        # calc_dcg returns a sum of a list of retrieved sections dcg scores
        # sum..dcgs.append(rel_grade / math.log2(i + 1)) (where i is the position in the list, starting at 1). order matters!
        # so for our eval data set this is =
        # (5/1) + (3/1.58) + (2/2) = 5 + 1.89 + 1 = 7.89 (ideal DCG, best possible order of relevance)
        # the acutal DCG in this test tho (since we are retreiving them in a suboptimal order) is =
        # (2/1) + (3/1.58) + (5/2) = 2 + 1.89 + 2.5 = 6.39
        # nDCG = actual DCG / ideal DCG = 6.39 / 7.89 = 0.81
        # a perfect score is always 1.0 (ideal = actual)

        # Assert
        self.assertEqual(r, 0.81)
