import threading
import os
from openai import OpenAI
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)


def call_chat_completions(prompt: str):
    completion = None

    def worker():
        nonlocal completion
        completion = client.chat.completions.create(
            model="gpt-4o",
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
        return completion.choices[0].message.content
