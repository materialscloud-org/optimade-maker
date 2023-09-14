ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# copy repo contents and install deps
COPY requirements.txt ./
RUN pip install -r requirements.txt

ENV UNIX_SOCK "/tmp/gunicorn.sock"

COPY run.sh /app/run.sh

ENV OPTIMADE_CONFIG_FILE ""

## Set the default config file path 
## Then copy the config from host to container
#ENV OPTIMADE_CONFIG_FILE "/config/config.yml"
#
#COPY optimade-config.yml  ${OPTIMADE_CONFIG_FILE}