FROM python:3.10-slim-buster
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn
# set time zone
ENV TZ=Europe/Stockholm

EXPOSE 8000
# make sure the entrypoint.sh is in unix format and executable
RUN apt-get update && apt-get install -y dos2unix && dos2unix ./entrypoint.sh && chmod +x entrypoint.sh


# create and use non-root user.. (requires us to use a port number higher than 1024)
RUN adduser \
  --disabled-password \
  --home /botrunner \
  --gecos '' botrunner \
  && chown -R botrunner /botrunner


## add necessary permissions
RUN chown -R botrunner:botrunner /app/servers/static/ && chmod -R 755 /app/servers/static/

USER botrunner

# entrypoint.sh makes sure the right env/config.js is replacing the config.js in ./servers/static
ENTRYPOINT ["/app/entrypoint.sh"]