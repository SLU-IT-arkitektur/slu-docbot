from fastapi.responses import JSONResponse
from .redis_store import RedisStore
from server import settings


def handle_feedback(feedback: str, comment: str, interaction_id: str, redis_store: RedisStore):
    feedback = feedback.lower()
    THUMBSUP = "thumbsup"
    THUMBSDOWN = "thumbsdown"

    if feedback != THUMBSUP and feedback != THUMBSDOWN:
        return JSONResponse(content={"message": f'Please enter {THUMBSUP} or {THUMBSDOWN}'}, status_code=400)

    if comment is not None and len(comment) > 300:
        return JSONResponse(content={"message": "Comment must be 300 characters or less"}, status_code=400)

    if comment is None or len(comment) == 0:
        comment = ""  # comment is optional

    interaction = redis_store.get_interaction(interaction_id)
    if interaction is None:
        return JSONResponse(content={"message": "Interaction not found"}, status_code=404)

    # update interaction with feedback and new expiration of 90 days
    interaction["feedback"] = feedback
    interaction["feedback_comment"] = comment
    redis_store.update_interaction(interaction, interaction_id)

    return {"message": settings.get_locale()["server_texts"]["thanks_for_feedback"]}
