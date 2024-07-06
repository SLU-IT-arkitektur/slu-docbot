from dotenv import load_dotenv
load_dotenv()  # this needs to be before some other imports
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
import logging
from server import settings
from .redis_store import RedisStore
from .feedback_handler import handle_feedback
from .query_handler import handle_query

logging.basicConfig(level=logging.INFO)
settings.check_required()   # .. or fail early!
settings.print_settings_with_defaults()
redis_store = RedisStore()
app = FastAPI()

static_folder = Path(__file__).parent / "static"


@app.get("/")
async def root():
    return FileResponse(static_folder / "index.html")


@app.get("/embeddings_version", status_code=200)
async def embeddings_version():
    version = redis_store.get_embeddings_version()
    resp = {
        'version': version
    }
    return resp


@app.get("/static/{file_name}")
async def static(file_name: str):
    return FileResponse(static_folder / file_name)


@app.get("/locale", status_code=200)
async def locale():
    locale = settings.get_locale()
    return locale["ui_texts"]


class QAPayload(BaseModel):
    query: str


@app.post("/qa", status_code=200)
async def qa(payload: QAPayload):
    return handle_query(payload.query, redis_store)


class FeedbackPayload(BaseModel):
    feedback: str
    interaction_id: str


@app.post("/feedback", status_code=200)
async def feedback(payload: FeedbackPayload):
    return handle_feedback(payload.feedback, payload.interaction_id, redis_store)
