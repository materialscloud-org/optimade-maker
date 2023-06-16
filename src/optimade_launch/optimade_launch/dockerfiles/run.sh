#!/bin/bash
mkdir -p logs
mkdir -p /tmp

touch logs/mc_optimade_access.log
touch logs/mc_optimade_error.log

tail -f -n 20 logs/mc_optimade_access.log logs/mc_optimade_error.log &
PORT=${PORT:-5000}

gunicorn \
    -w 2 \
    -k uvicorn.workers.UvicornWorker \
    --error-logfile logs/mc_optimade_error.log \
    --access-logfile logs/mc_optimade_access.log \
    --capture-output \
    --access-logformat "%(t)s: %(h)s %(l)s %(u)s %(r)s %(s)s %(b)s %(f)s %(a)s" \
    -b unix:/tmp/${SOCKET_NAME}.sock optimade.server.main:app
    -b :${PORT} optimade.server.main:app