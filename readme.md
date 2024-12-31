# slu-docbot

This is a QA bot that can answer questions about a given document. In this example it is specialized to answer questions about the document ***Utbildningshandboken (Policy, regler och riktlinjer för utbildning på grundnivå och avancerad nivå vid SLU)***. The bot has support for multiple languages.

## overview

Here’s a high-level overview of the system's components and how they interact:

```
                      +----------------------------+
                      |     User/Client Input      |
                      +----------------------------+
                                  |
                                  v
                     +-----------------------------+
                     |          QA Bot             |
                     |  - Receives questions       |
                     |  - Searches embeddings      |
                     |  - Queries LLM API          |
                     +-----------------------------+
                                  |
                                  v
        +----------------------------+       +-----------------------------+
        |          Redis             |<------|    Embeddings Updater       |
        |  - Stores embeddings       |       |  - Creates sections         |
        |  - Temporary interactions  |       |  - Generates embeddings     |
        +----------------------------+       |  - Updates Redis store       |
                               ^             +-----------------------------+
                               |                        |
                               |                        v
                               |             +-----------------------------+
                               |             |    Quality Assurance         |
                               |             | - Verifies new embeddings    |
                               |             | - Ensures data quality       |
                               |             +-----------------------------+
                               |
                     +-----------------------------+
                     |         Datapump            |
                     |  - Transfers interactions   |
                     |    from Redis to StatsDB    |
                     +-----------------------------+
                                  |
                                  v
                     +-----------------------------+
                     |    PostgreSQL (StatsDB)     |
                     | - Persistent interaction    |
                     |   storage for reporting     |
                     +-----------------------------+
                                  |
                                  v
                     +-----------------------------+
                     |          Reporter           |
                     |  - Generates reports        |
                     |  - Sends reports via email  |
                     +-----------------------------+


   +----------------------------------------------------+
   |                    Evaluator                       |
   |  - Measures retrieval performance of the system    |
   |  - Metrics: recall@k, precision@k, nDCG@k          |
   +----------------------------------------------------+
```


## prerequisites
- a local k8s cluster, e.g [docker desktop](https://www.docker.com/products/docker-desktop/) (with kubernetes **"enabled"**)  
- [skaffold](https://skaffold.dev/) (for building and deploying the app to the cluster)
- python 3.11.x
- an OpenAI API key 

## get started
- create a virtual environment: `python3.11 -m venv env`   
- create a .env file in the root of this project with the following content:
```
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = 'mysecretpassword'
OPENAI_API_KEY = 'REPLACE_WITH_YOUR_OPENAI_API_KEY'
PROMPT_INST = 'REPLACE_WITH_YOUR_PROMPT'
PROMPT_INST_EN = 'REPLACE_WITH_YOUR_EN_PROMPT'
```  
- activate the virtual environment: `source env/bin/activate`   
- install dependencies: `pip install -r requirements.txt`  
- in devops/k8s/local create a file called openai-secret.yaml with the following content:  
```
apiVersion: v1
kind: Secret
metadata:
  name: openai
type: Opaque
stringData:
  api-key: REPLACE_WITH_YOUR_OPENAI_API_KEY
```  

- in devops/k8s/local create a file called prompt-secret.yaml with the following content:  
```
apiVersion: v1
kind: Secret
metadata:
  name: prompt
type: Opaque
stringData:
  instructions: REPLACE_WITH_YOUR_PROMPT
  instructions-en: REPLACE_WITH_YOUR_EN_PROMPT

```  


## run locally in Kubernetes
1. activate the virtual environment: `source env/bin/activate`
2. run: `skaffold run --tail`  
  or if you want you can stand up redis-stack only with `skaffold run -f skaffold.exclude.bot.yaml` and run the bot locally with reloading by running `./bot.sh`

3. run: (**news!**) see *run embeddings_updater* below 

... you can also run: `python docx_to_redis_embeddings.py` to populate redis with embeddings *(repeat this step between skaffold delete's)*  
... and you can also run `python web_to_redis_embeddings.py` to populate redis with embeddings by scraping the web version     

4. now go to localhost:8000 in your browser and ask away..

In both scenarios (*skaffold.yaml and skaffold.exclude.bot.yaml*) redis persists data in a volume mounted to the redis container. This means that you can stop and start the bot without having to re-populate redis with embeddings.
If you want to reset redis you can run: `skaffold delete` and then `skaffold run --tail` again.  


## how this works
1) We first parse the word document and extract sections. Sections are pairs of a heading and the text that follows it. We yield these pairs as a stream of tuples. **See ./section_creators/docx_parser.py**

2) We then use the openai API to create [embeddings](https://www.pinecone.io/learn/vector-embeddings/) for each section. We store these embeddings in redis. This is done in a seperate module that subscribes to the stream of tuples from the previous step. **See ./embeddings_stores/redis_store.py**  

3) We now have a redis database with embeddings for each section and can search for the most similar section to a given question.
We do this by first creating an embedding for the question and then comparing it to all the embeddings in the database. We use the cosine similarity metric for this.

4) When we have found the most similar sections we pass them as context to the openai API along with the question we want answered. The openai API will then return the answer based only on the provided context.  
  
This technique is called [Retrieval-Augmented Generation (RAG)](https://arxiv.org/abs/2005.11401). 

*We use a blue-green-setup for the embeddings where one index is being used by the chatbot while the other can be updated (see "run embeddings_updater" below)*


## run embeddings_updater
The embeddings_updater is a script that will perform the following steps when executed:

1. delete the passive sections so they can be recreated with new embeddings 
2. scrape the target website and creates sections 
3. pipes the sections as they are being created into our redis embeddings store (i.e create embeddings for each section)
4. when new embeddings have been created the script runs Quality Assurance tests (verifies that answers based on the newly created embeddings are similar enough to the answers in qa_qa.json)   
5. if all tests pass we set the passive index to active 
6. ... and delete the semantic cache entries (since we now have new fresh embeddings)
7. finally we set the current date as the embeddings_version 

It is executed as a Kubernetes CronJob (on a configurable interval) in the test/prod environment but you can also run it locally either by running `python embeddings_updater.py` or `skaffold run -f skaffold.embeddings_updater.one.off.yaml` (both requires the chatbot to be up and running via `skaffold run`)

## run the datapump
The datapump transfers interactions from Redis to the StatsDB (PostgreSQL). Interactions are temporarily stored in Redis and then permanently persisted in StatsDB for reporting and analytics.
### how the datapump runs
- **Test/Production**: Runs as a Kubernetes CronJob.
- **Local Execution**: You can run it locally with the following command:  
  ```bash
  skaffold run -f skaffold.datapump.one.off.yaml --tail
  ```
  
### before running locally 
- make sure the QA bot is running (skaffold run)  
- make sure you have created (and kubectl applied..) this file: ``./devops/k8s/local/postgres-secret.yaml`` with this content:  
```
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
type: Opaque
stringData:
  connection_string: dbname=statsdb user=localdevuser password=localdevpassword host=postgres
```

## run the reporter
check the [reports readme](./reports/readme.md)

## run the evaluator

The evaluator assesses the retrieval performance of this RAG application by calculating the following metrics:

- **recall@k**: Measures coverage by evaluating how many relevant sections are returned among the top-k results (binary relevance, order unaware).
- **precision@k**: Measures accuracy by evaluating how many of the retrieved sections are relevant (binary relevance, order unaware).
- **nDCG@k**: Measures ranking quality by evaluating the order of retrieved sections based on graded relevance (order aware).

### prerequisites
Ensure the following before running the evaluator:
- Redis is running and populated with sections data.
- The evaluation dataset (`evaluation_data_set.json`) exists in the `./data/` directory.

### how to run
The evaluator can be run as a standalone script or imported as a module. By default, it calculates metrics for the top-3 results (`k=3`):

```bash
python evaluator.py
```

## tests
run ```python -m unittest discover``` in the root of this project
