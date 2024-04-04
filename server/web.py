from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
import logging
from fastapi import Depends
from fastapi.security import HTTPBasicCredentials
from server import settings
from .auth import authenticate
from .redis_store import RedisStore
from .feedback_handler import handle_feedback
from .query_handler import handle_query
load_dotenv()

logging.basicConfig(level=logging.INFO)
settings.check_required()   # .. or fail early!
settings.print_settings_with_defaults()
redis_store = RedisStore()
app = FastAPI()

static_folder = Path(__file__).parent / "static"


@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(authenticate)):
    return FileResponse(static_folder / "index.html")


@app.get("/static/{file_name}")
async def static(file_name: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    return FileResponse(static_folder / file_name)


class QAPayload(BaseModel):
    query: str


@app.post("/qa", status_code=200)
async def qa(payload: QAPayload, credentials: HTTPBasicCredentials = Depends(authenticate)):
    return handle_query(payload.query, redis_store)


class FeedbackPayload(BaseModel):
    feedback: str
    interaction_id: str


@app.post("/feedback", status_code=200)
async def feedback(payload: FeedbackPayload, credentials: HTTPBasicCredentials = Depends(authenticate)):
    return handle_feedback(payload.feedback, payload.interaction_id, redis_store)
