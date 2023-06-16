FROM ghcr.io/materials-consortia/optimade:0.24.0

# copy repo contents and install deps
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY run.sh /app/run.sh

ENV OPTIMADE_CONFIG_FILE ""