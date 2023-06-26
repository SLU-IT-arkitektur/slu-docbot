import logging
import os

prompt_instructions = os.getenv('PROMPT_INST')
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')
correct_username = os.getenv('USERNAME')
correct_password = os.getenv('PASSWORD')

def check_required():
    if prompt_instructions is None:
        logging.info("Error: PROMPT_INST is not set")
        exit(1)
    if redis_host is None:
        logging.info("Error: REDIS_HOST is not set")
        exit(1)
    if redis_port is None:
        logging.info("Error: REDIS_PORT is not set")
        exit(1)
    if redis_password is None:
        logging.info("Error: REDIS_PASSWORD is not set")
        exit(1)
    if correct_username is None:
        logging.info("Error: USERNAME is not set")
        exit(1)
    if correct_password is None:
        logging.info("Error: PASSWORD is not set")
        exit(1)
    logging.info('Settings initialized')
    
