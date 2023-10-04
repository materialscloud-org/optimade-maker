#!/usr/bin/env python3

"""
This file (re)generates the apache hosts file for the active site
with all needed redirects for the various existing containers.

requirements: the `docker` python package
"""
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import docker

### STATIC CONFIGURATION

main_template = """
DirectoryIndex index.php index.html

<VirtualHost *:80>
  ServerName {SERVER_NAME}

  DocumentRoot "/var/www/html"
  <Directory "/var/www/html">
    AllowOverride All
    Options -Indexes +FollowSymLinks
    Require all granted
  </Directory>

  Alias /.well-known/acme-challenge /var/www/letsencrypt/.well-known/acme-challenge
  <Directory /var/www/letsencrypt/.well-known/acme-challenge>
    Order allow,deny
    Allow from all
  </Directory>

  # redirect all traffic to SSL, unless a specific VirtualHost for *:80 is specified,
  # which would take precedence over the default virtual host.
  # Make an exception for the location required for the Letsencrypt/ACME client challenge file
  RewriteEngine on
  RewriteCond %{{HTTPS}} !=on
  RewriteCond %{{REQUEST_URI}} !/.well-known/acme-challenge
  RewriteRule .* https://%{{SERVER_NAME}}%{{REQUEST_URI}} [R=301,L]

</VirtualHost>

<VirtualHost *:443>
  ServerName {SERVER_NAME}

  SSLEngine on
  SSLCipherSuite AES256+EECDH:AES256+EDH
  SSLProtocol All -SSLv2 -SSLv3 -TLSv1
  SSLHonorCipherOrder On
  SSLCompression off
  SSLCertificateFile /etc/letsencrypt/live/{SERVER_NAME}/fullchain.pem
  SSLCertificateKeyFile /etc/letsencrypt/live/{SERVER_NAME}/privkey.pem

  DocumentRoot "/var/www/html"
  <Directory "/var/www/html">
    AllowOverride All
    Options -Indexes +FollowSymLinks
    Require all granted
  </Directory>

  SSLProxyEngine on
  RewriteEngine on

  # ---------------------------
  # index metadb
  ProxyPass /index http://localhost:{INDEX_METADB_PORT}
  ProxyPassReverse /index http://localhost:{INDEX_METADB_PORT}
  # ---------------------------

  {CONTAINER_REDIRECTS}

</VirtualHost>
"""

template_container_redirect = """
  RewriteRule ^/{URL}$ /{URL}/ [R=301,L]
  <Location /{URL}>
    ProxyPreserveHost  On
    ProxyPass http://localhost:{PORT} upgrade=ANY
    ProxyPassReverse http://localhost:{PORT}
    RequestHeader set X-Script-Name /{URL}
    RequestHeader set X-Scheme https
  </Location>
"""


def _get_url_from_container_name(name):
    doi_id = name.split("optimade_")[1]
    return f"archive/{doi_id}"


def get_container_metas():
    container_metas = []
    running_containers = docker.DockerClient().containers.list()
    for container in running_containers:
        if not container.name.startswith("optimade_"):
            logger.info(f"Skipping {container.name}, not an OPTIMADE container!")
            continue

        try:
            host_ports = container.ports["5000/tcp"]
        except KeyError:
            logger.info(
                f"[NO VALID PORT] Skipping {container.name=} with {container.image.tags=}, {container.ports=}"
            )
            continue

        host_port = None
        if host_ports is not None:
            for host_port_meta in host_ports:
                if host_port_meta["HostIp"] == "0.0.0.0":
                    host_port = host_port_meta["HostPort"]
                    break
        if host_port is None:
            logger.info(
                f"[NO PORT EXPOSED ON 0.0.0.0] Skipping {container.name=} with {container.image.tags=}, {container.ports=}"
            )
            continue

        try:
            url = _get_url_from_container_name(container.name)
        except ValueError:
            logger.info(
                f"[INVALID CONTAINER NAME] Skipping {container.name=}, invalid prefix"
            )
            break

        logger.info(f">> {container.short_id=}, {container.name=}, {host_port=}")

        container_metas.append({"URL": url, "PORT": host_port})

    return container_metas


def generate_vhosts(server_name="optimade.materialscloud.org", index_port=3214):
    container_redirects = []
    for container_meta in get_container_metas():
        container_redirects.append(template_container_redirect.format(**container_meta))

    vhosts_file = main_template.format(
        SERVER_NAME=server_name,
        INDEX_METADB_PORT=index_port,
        CONTAINER_REDIRECTS="\n\n".join(container_redirects),
    )
    return vhosts_file


if __name__ == "__main__":
    print(generate_vhosts())
