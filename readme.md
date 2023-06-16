# slu-docbot

This is a QA bot that can answer questions about a given document. In this example it is specialized to answer questions about the document ***Utbildningshandboken (Policy, regler och riktlinjer för utbildning på grundnivå och avancerad nivå vid SLU)***.

## prerequisites
- a local k8s cluster, e.g [docker desktop](https://www.docker.com/products/docker-desktop/) (with kubernetes **"enabled"**)  
- [skaffold](https://skaffold.dev/) (for building and deploying the app to the cluster)
- python 3.10.x
- an OpenAI API key 

## get started
- create a virtual environment: `python3 -m venv env`   
- create a .env file in the root of this project with the following content:
```
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = 'mysecretpassword'
OPENAI_API_KEY = 'REPLACE_WITH_YOUR_OPENAI_API_KEY'
PROMPT_INST = 'REPLACE_WITH_YOUR_PROMPT'
USERNAME = 'admin'
PASSWORD = 'admin'

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

```  


## run locally in Kubernetes
- activate the virtual environment: `source env/bin/activate`
- run: `skaffold run --tail`  
  or if you want you can stand up redis-stack only with `skaffold run -f skaffold.exclude.bot.yaml` and run the bot locally with reloading by running `./bot.sh`
- run: `python docx_to_redis_embeddings.py` to populate redis with embeddings *(repeat this step between skaffold delete's)*
- now go to localhost:8000 in your browser and ask away..

In both scenarios (*skaffold.yaml and skaffold.exclude.bot.yaml*) redis persists data in a volume mounted to the redis container. This means that you can stop and start the bot without having to re-populate redis with embeddings.
If you want to reset redis you can run: `skaffold delete` and then `skaffold run --tail` again.  


## how this works
1) We first parse the word document and extract sections. Sections are pairs of a heading and the text that follows it. We yield these pairs as a stream of tuples. **See ./data_retrievers/parse_docx.py**

2) We then use the openai API to create [embeddings](https://www.pinecone.io/learn/vector-embeddings/) for each section. We store these embeddings in redis. This is done in a seperate module that subscribes to the stream of tuples from the previous step. **See ./embeddings_creators/to_redis.py**  

3) We now have a redis database with embeddings for each section and can search for the most similar section to a given question.
We do this by first creating an embedding for the question and then comparing it to all the embeddings in the database. We use the cosine similarity metric for this.

4) When we have found the most similar sections we pass them as context to the openai API along with the question we want answered. The openai API will then return the answer based only on the provided context.  
  
This technique is called [Retrieval-Augmented Generation (RAG)](https://arxiv.org/abs/2005.11401). 

## tests
run ```python -m unittest discover``` in the root of this project
