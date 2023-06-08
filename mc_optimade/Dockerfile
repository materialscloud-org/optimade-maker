FROM python:3.11-slim

# Prevent writing .pyc files on the import of source modules
# and set unbuffered mode to ensure logging outputs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copy repo contents and install dependencies
COPY src/jsonl_server/* ./
RUN apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# run script to inject the data
ENV JSONL_SOURCE="optimade.jsonl"
COPY ${JSONL_SOURCE} ./

CMD [ "python", "load_data.py"]