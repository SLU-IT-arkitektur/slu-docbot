#!/bin/sh
cp  /app/servers/static/_configs/${SPAENVIRONMENT}/config.js /app/servers/static/
gunicorn -w 4 -k uvicorn.workers.UvicornWorker servers.web:app --bind 0.0.0.0:8000 --timeout 120

