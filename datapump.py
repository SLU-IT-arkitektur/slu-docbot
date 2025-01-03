from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import psycopg
import os
from server.redis_store import RedisStore
from server import settings
import logging

redis_store = None
LAST_COPIED_TIMESTAMP_KEY = 'last_copied_timestamp'


def init():
    logging.basicConfig(level=logging.INFO)
    settings.check_required()   # .. or fail early!
    settings.print_settings_with_defaults()
    global redis_store
    redis_store = RedisStore()
    logging.info('starting data pump')


def get_last_copied_timestamp_or_default(cur):
    cur.execute(f"SELECT value FROM stats_metadata WHERE key = '{LAST_COPIED_TIMESTAMP_KEY}'")
    last_copied_timestamp = cur.fetchone()
    if last_copied_timestamp:
        last_copied_timestamp = last_copied_timestamp[0]
    else:
        last_copied_timestamp = '1970-01-01 00:00:00'

    last_copied_timestamp = datetime.strptime(last_copied_timestamp, "%Y-%m-%d %H:%M:%S")
    logging.info(f"Last copied timestamp: {last_copied_timestamp}")
    return last_copied_timestamp


def should_already_be_copied(last_copied_timestamp, all_interactions, key_interaction):
    timestamp = all_interactions[key_interaction]['timestamp']
    # adding one hour to the timestamp to avoid missing
    # any interactions (if already exist we will skip it)
    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    timestamp = timestamp + timedelta(hours=1)
    if timestamp <= last_copied_timestamp:
        logging.info(f"interaction {key_interaction} with timestamp {timestamp} should already be copied, skipping..")
        return True
    else:
        logging.info(f"interaction {key_interaction} with timestamp {timestamp} should be copied now")
        return False


def copy_interaction_to_statsdb(cur, key_interaction, all_interactions):
    logging.info(f"copying over {key_interaction} from redis to postgres (statsdb)")
    interaction = all_interactions[key_interaction]
    logging.info(f"interaction: {interaction}")
    if 'feedback_comment' not in interaction or interaction['feedback_comment'] is None:
        interaction['feedback_comment'] = ''

    cur.execute('''INSERT INTO
                               interactions
                               (redis_key,
                               redis_timestamp,
                               query,
                               reply,
                               feedback,
                               feedback_comment,
                               request_duration_in_seconds,
                               chat_completions_req_duration_in_seconds)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (redis_key) DO NOTHING''',
                (key_interaction,
                 interaction['timestamp'],
                 interaction['query'],
                 interaction['reply'],
                 interaction['feedback'],
                 interaction['feedback_comment'],
                 interaction['request_duration_in_seconds'],
                 interaction['chat_completions_req_duration_in_seconds']))


def upsert_last_copied_timestamp(cur, now_timestamp):
    logging.info(f"\n\nupdating last copied timestamp to {now_timestamp}\n\n")
    cur.execute(f'''INSERT INTO stats_metadata (key, value)
       VALUES ('{LAST_COPIED_TIMESTAMP_KEY}', %s)
       ON CONFLICT (key) DO UPDATE
       SET value = EXCLUDED.value''', (now_timestamp,))


def run():
    try:
        init()
        all_interactions = redis_store.get_all_interactions_with_keys()

        connection_string = os.getenv('STATSDB_CONNECTION_STRING')
        if connection_string is None:
            logging.error("STATSDB_CONNECTION_STRING is not set in env vars")
            exit(1)
        else:
            logging.info("using connection string from env var STATSDB_CONNECTION_STRING")

        with psycopg.connect(connection_string) as conn:
            try:
                now_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn.cursor() as cur:
                    last_copied_timestamp = get_last_copied_timestamp_or_default(cur)
                    for key_interaction in all_interactions:
                        if should_already_be_copied(last_copied_timestamp, all_interactions, key_interaction):
                            continue
                        copy_interaction_to_statsdb(cur, key_interaction, all_interactions)

                    # after all interactions are copied, update the last copied timestamp
                    upsert_last_copied_timestamp(cur, now_timestamp)

                # then commit transaction (new last_copied_timestamp and all inserts or nothing)
                conn.commit()
            except Exception as e:
                logging.error(f"Error during transaction: {e}")
                conn.rollback()
                raise e

    except Exception as e:
        logging.critical(f"Critical error in datapump.py: {str(e)}", exc_info=True)


run()
