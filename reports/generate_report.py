import redis
import time
import os
import jinja2
from datetime import datetime
from redis.commands.search.query import Query
from dotenv import load_dotenv
load_dotenv()

redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')


def try_connect_to_redis(max_attempts=10, delay_in_seconds=5):
    for i in range(max_attempts):
        try:
            conn = redis.Redis(host=redis_host, port=redis_port,
                               password=redis_password, encoding='utf-8', decode_responses=True)
            if conn.ping():
                print("connected to redis")
                return conn
        except redis.ConnectionError as e:
            attempt = i + 1
            if attempt >= max_attempts:
                print(f'failed with {e}')
                raise
            else:
                print(f'failed to connect to redis with error {e}, will retry (attempt {attempt}/{max_attempts}) in {delay_in_seconds} seconds')
                print('sleeping 5 seconds before trying again..')
                time.sleep(5)
                continue


conn = try_connect_to_redis()


def get_number_of_interactions():
    # get number of interactions
    numberOfInteractions = conn.ft("interaction").info().get('num_docs')
    return numberOfInteractions


def get_number_of_interactions_with_thumbs_up():
    # get number of interactions with thumbsUp feedback
    numberOfInteractionsWithThumbsUp = conn.ft("interaction").search('@feedback:thumbsup').total
    return numberOfInteractionsWithThumbsUp


def get_number_of_interactions_with_thumbs_down():
    # get number of interactions with thumbsDown feedback
    numberOfInteractionsWithThumbsDown = conn.ft("interaction").search('@feedback:thumbsdown').total
    return numberOfInteractionsWithThumbsDown


def get_all_thumbs_up():
    # get all interactions with tumbsUp feedback
    total = get_number_of_interactions_with_thumbs_up()
    q = Query("@feedback:thumbsup").paging(0, total)
    thumbsUps = conn.ft("interaction").search(q)
    return thumbsUps.docs


def get_all_thumbs_down():
    # get all interactions with tumbsDown feedback
    total = get_number_of_interactions_with_thumbs_down()
    q = Query("@feedback:thumbsdown").paging(0, total)
    thumbsDowns = conn.ft("interaction").search(q)
    return thumbsDowns.docs


def generate_report():
    generated_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'Report generated at {generated_timestamp}')
    numberOfInteractions = get_number_of_interactions()
    print("Number of interactions (with or without feedback, saved for 7 days): ", numberOfInteractions)

    numberOfThumbsUps = get_number_of_interactions_with_thumbs_up()
    print("Number of interactions with thumbsUp feedback (saved for 90 days): ", numberOfThumbsUps)

    numberOfThumbsDowns = get_number_of_interactions_with_thumbs_down()
    print("Number of interactions with thumbsDown feedback (saved for 90 days): ", numberOfThumbsDowns)

    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))
    template = template_env.get_template("simple.html")

    thumbsUps = get_all_thumbs_up()
    thumbsUps = sorted(thumbsUps, key=lambda x: x['timestamp'], reverse=True)  # newest first
    thumbsDowns = get_all_thumbs_down()
    thumbsDowns = sorted(thumbsDowns, key=lambda x: x['timestamp'], reverse=True)  # newest first

    report = template.render(generated_timestamp=generated_timestamp, numberOfInteractions=numberOfInteractions, numberOfThumbsUps=numberOfThumbsUps, numberOfThumbsDowns=numberOfThumbsDowns, thumbsUps=thumbsUps, thumbsDowns=thumbsDowns)
    with open('report.html', 'w') as f:
        f.write(report)

    print("saved ./report.html")


if __name__ == "__main__":
    generate_report()
