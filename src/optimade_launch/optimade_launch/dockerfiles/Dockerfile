FROM ghcr.io/materials-consortia/optimade:0.24.0

# copy repo contents and install deps
COPY requirements.txt ./
RUN pip install -r requirements.txt

ENV SOCKET_NAME "gunicorn"
ENV PORT 5000

COPY run.sh /app/run.sh

ENV OPTIMADE_CONFIG_FILE ""