import threading
import openai


def call_chat_completions(prompt: str):
    response = None

    def worker():
        nonlocal response
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            temperature=0.0,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=25)  # give open ai 25 seconds to respond

    if thread.is_alive():
        raise TimeoutError("OpenAI API call took to long")
    else:
        return response
