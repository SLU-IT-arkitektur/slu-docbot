#!/bin/sh
cp  /app/server/static/_configs/${SPAENVIRONMENT}/config.js /app/server/static/
gunicorn -w 4 -k uvicorn.workers.UvicornWorker server.web:app --bind 0.0.0.0:8000 --timeout 120

