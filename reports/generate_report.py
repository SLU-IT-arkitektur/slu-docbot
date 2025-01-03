import os
import jinja2
from datetime import datetime
import psycopg
import logging
from dotenv import load_dotenv
load_dotenv()


def connect_to_postgres():
    """
    Establish a connection to the PostgreSQL database using an environment variable for the connection string.
    """
    connection_string = os.getenv('STATSDB_CONNECTION_STRING')
    if connection_string is None:
        logging.error("STATSDB_CONNECTION_STRING is not set")
        exit(1)
    else:
        logging.info("Using connection string from env var STATSDB_CONNECTION_STRING")

    try:
        conn = psycopg.connect(connection_string)
        return conn
    except Exception as e:
        logging.critical(f"Failed to connect to PostgreSQL: {e}")
        raise


def get_number_of_interactions(cur):
    # get number of interactions from statsdb
    cur.execute("SELECT COUNT(*) FROM interactions")
    numberOfInteractions = cur.fetchone()['count']
    return numberOfInteractions


def get_number_of_interactions_with_thumbs_up(cur):
    # get number of interactions with thumbsUp feedback
    cur.execute("SELECT COUNT(*) FROM interactions WHERE feedback = 'thumbsup'")
    numberOfInteractionsWithThumbsUp = cur.fetchone()['count']
    return numberOfInteractionsWithThumbsUp


def get_number_of_interactions_with_thumbs_down(cur):
    # get number of interactions with thumbsDown feedback
    cur.execute("SELECT COUNT(*) FROM interactions WHERE feedback = 'thumbsdown'")
    numberOfInteractionsWithThumbsDown = cur.fetchone()['count']
    return numberOfInteractionsWithThumbsDown


def get_all_thumbs_up_statsdb(cur):
    # get all interactions with tumbsUp feedback
    cur.execute("SELECT * FROM interactions WHERE feedback = 'thumbsup'")
    thumbsUps = cur.fetchall()
    return thumbsUps


def get_all_thumbs_down_statsdb(cur):
    # get all interactions with tumbsDown feedback
    cur.execute("SELECT * FROM interactions WHERE feedback = 'thumbsdown'")
    thumbsDowns = cur.fetchall()
    return thumbsDowns


def generate_report():
    try:
        with connect_to_postgres() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                generated_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f'Report generated at {generated_timestamp}')
                number_of_interactions = get_number_of_interactions(cur)
                print("Total number of interactions: ", number_of_interactions)

                number_of_thumbsup = get_number_of_interactions_with_thumbs_up(cur)
                print("Number of interactions with thumbsUp feedback: ", number_of_thumbsup)

                number_of_thumbsdown = get_number_of_interactions_with_thumbs_down(cur)
                print("Number of interactions with thumbsDown feedback: ", number_of_thumbsdown)

                template_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))
                template = template_env.get_template("simple.html")

                thumbsUps = get_all_thumbs_up_statsdb(cur)
                thumbsUps = sorted(thumbsUps, key=lambda x: x['redis_timestamp'], reverse=True)  # newest first
                thumbsDowns = get_all_thumbs_down_statsdb(cur)
                thumbsDowns = sorted(thumbsDowns, key=lambda x: x['redis_timestamp'], reverse=True)  # newest first

                report = template.render(generated_timestamp=generated_timestamp,
                                         numberOfInteractions=number_of_interactions,
                                         numberOfThumbsUps=number_of_thumbsup,
                                         numberOfThumbsDowns=number_of_thumbsdown,
                                         thumbsUps=thumbsUps,
                                         thumbsDowns=thumbsDowns)

                with open('report.html', 'w') as f:
                    f.write(report)
                print("saved ./report.html")

    except Exception as e:
        logging.critical(f"Critical error in generate_report.py: {str(e)}", exc_info=True)


if __name__ == "__main__":
    generate_report()
