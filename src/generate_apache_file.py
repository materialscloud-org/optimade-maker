"""
This file (re)generates the apache hosts file for the active site
with all needed redirects for the various existing containers.

requirements: the `docker` python package
"""
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

### CONFIGURABLE CONFIGURATION
SERVER_NAME = "archive-live-optimade.materialscloud.org" # Used to generate the Apache file
DEMO_MODE = False # If True, do not check docker containers but just return fake data

# Only filter containers from these images; must be a set
VALID_IMAGE_TAGS = {'optimade-python-tools-server:latest'} # TODO REPLACE HERE WITH CORRECT (SET OF) BASE IMAGE NAME(S)
# Check the exposed port pointing to this internal port in the container; skip if this port is not exposed, or if
# it is not exposed to 0.0.0.0 in the Host
INTERNAL_WEB_PORT = '5000/tcp'


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
  DocumentRoot "/var/www/html"

  SSLEngine on
  SSLCipherSuite AES256+EECDH:AES256+EDH
  SSLProtocol All -SSLv2 -SSLv3 -TLSv1
  SSLHonorCipherOrder On
  SSLCompression off
  SSLCertificateFile /etc/letsencrypt/live/{SERVER_NAME}/fullchain.pem
  SSLCertificateKeyFile /etc/letsencrypt/live/{SERVER_NAME}/privkey.pem

  <Directory "/var/www/html">
    AllowOverride All
    Options -Indexes +FollowSymLinks
    Require all granted
  </Directory>

  SSLProxyEngine on
  RewriteEngine on

  {CONTAINER_REDIRECTS}

</VirtualHost>
"""

template_container_redirect = """
  RewriteRule ^/{URL}$ /{URL}/ [R=301,L]
  <Location /{URL}>
    ProxyPreserveHost  On
    ProxyPass http://localhost:{PORT}/ upgrade=ANY
    ProxyPassReverse http://localhost:{PORT}/    
    RequestHeader set X-Script-Name /{URL}
    RequestHeader set X-Scheme https
  </Location>
"""

####
# FUNCTIONALITY

def get_url_from_container_name(name, url_prefix=''):
    """Given the container name, extract back the part of the URL.

    This URL part will be used in apache redirects.
    
    The rule is the following. For a DOI like:

        https://doi.org/10.24435/materialscloud:qt-4b

    potential urls:

       10.24435/materialscloud:qt-4b
       10.24435/materialscloud:2017.0008/v1

    because container name doesn't allow '/', ':', ...
    consider a mapping from url to container name by

    _ -> _u_
    : -> _c_
    / -> _s_

    (Note: currently not implemented!)
    
    We then accept only container names starting with `10.24435_` and the URL
    is obtained from the rest, possibly prepending an URL prefix (from the
    kwargs of this function)
    """
    valid_prefix = '10.24435_'
    if not name.startswith(valid_prefix):
        raise ValueError("Invalid container name")
    
    return f'{url_prefix}{name.replace("=", ":")[len(valid_prefix):]}'

def get_container_metas(demo=False):
    if demo:
        return [
            {
                "URL": "url1",
                "PORT": "12341",
            },
            {
                "URL": "url2",
                "PORT": "12342",
            },
        ]

    import docker

    container_metas = []

    client = docker.from_env()
    # Only running ones
    containers = client.containers.list()
    for container in containers:
        if not VALID_IMAGE_TAGS.intersection(container.image.tags):
            # Probably there is a better way to filter in list(), for now I
            # just skip anything that does not start from one of the provided tags
            logger.info(f"[INCOMPATIBLE IMAGE] Skipping {container.name=} with {container.image.tags=}")
            continue

        try:
            host_ports = container.ports[INTERNAL_WEB_PORT]
        except KeyError:            
            logger.info(f"[NO VALID PORT] Skipping {container.name=} with {container.image.tags=}, {container.ports=}")
            continue
        
        host_port = None
        for host_port_meta in host_ports:
            if host_port_meta['HostIp'] == '0.0.0.0':
                host_port = host_port_meta['HostPort']
                break
        if host_port is None:
            logger.info(f"[NO PORT EXPOSED ON 0.0.0.0] Skipping {container.name=} with {container.image.tags=}, {container.ports=}")
            break

        try:
            url = get_url_from_container_name(container.name)
        except ValueError as exc:
            logger.info(f'[INVALID CONTAINER NAME] Skipping {container.name=}, invalid prefix')
            break

        logger.info(f'>> {container.short_id=}, {container.name=}, {host_port=}')

        container_metas.append({
            "URL": url,
            "PORT": host_port
        })

    return container_metas


def generate_vhosts(demo):
    container_redirects = []
    for container_meta in get_container_metas(demo=demo):
        container_redirects.append(template_container_redirect.format(
            **container_meta
        ))

    vhosts_file = main_template.format(
        SERVER_NAME = SERVER_NAME,
        CONTAINER_REDIRECTS = "\n\n".join(container_redirects)
    )
    return vhosts_file

if __name__ == "__main__":
    #print(generate_vhosts(demo=DEMO_MODE))
    print(get_container_metas(demo=DEMO_MODE))
