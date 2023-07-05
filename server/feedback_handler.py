from datetime import timedelta
from fastapi.responses import JSONResponse
from .redis_store import RedisStore

def handle_feedback(feedback: str, interaction_id: str, redis_store: RedisStore):
    feedback = feedback.lower()
    THUMBSUP = "thumbsup"
    THUMBSDOWN = "thumbsdown"
    if feedback != THUMBSUP and feedback != THUMBSDOWN:
        return JSONResponse(content={"message": f'Please enter {THUMBSUP} or {THUMBSDOWN}'}, status_code=400)

    interaction = redis_store.get_interaction(interaction_id)
    if interaction is None:
        return JSONResponse(content={"message": "Interaction not found"}, status_code=404)

    # update interaction with feedback and new expiration of 90 days
    interaction["feedback"] = feedback
    redis_store.update_interaction(interaction, interaction_id, timedelta(days=90))

    return {"message": "Tack för din feedback!"}