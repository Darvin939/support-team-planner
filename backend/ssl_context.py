import atexit
import logging
import os
import shutil
import ssl
import stat
import tempfile
from json import loads as json_load

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CERT_DIR = None
logger = logging.getLogger(__name__)


class TLSConfigurationError(RuntimeError):
    """A configured certificate pair exists but cannot be used for HTTPS."""


def _get_cert_dir():
    global _CERT_DIR
    if _CERT_DIR is None:
        _CERT_DIR = tempfile.mkdtemp(prefix='app_certs_')
        atexit.register(shutil.rmtree, _CERT_DIR, ignore_errors=True)
    return _CERT_DIR


def _validate_cert_pair(cert_path, key_path):
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # A callback prevents OpenSSL from prompting on stdin for encrypted keys.
        context.load_cert_chain(cert_path, key_path, password=lambda: b'')
    except (OSError, ValueError):
        raise TLSConfigurationError(
            'Unable to load TLS certificate and key: expected readable PEM files '
            'with a matching, unencrypted private key'
        ) from None


def _get_mounted_cert():
    cert_path = os.environ.get('SUPPORT_PLANNER_TLS_CERT_FILE')
    key_path = os.environ.get('SUPPORT_PLANNER_TLS_KEY_FILE')
    if not cert_path or not key_path:
        return None, None
    try:
        file_stats = [os.stat(path) for path in (cert_path, key_path)]
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError):
        raise TLSConfigurationError(
            'Unable to access SUPPORT_PLANNER_TLS_CERT_FILE/SUPPORT_PLANNER_TLS_KEY_FILE'
        ) from None
    if not all(stat.S_ISREG(info.st_mode) for info in file_stats):
        raise TLSConfigurationError(
            'SUPPORT_PLANNER_TLS_CERT_FILE and SUPPORT_PLANNER_TLS_KEY_FILE must be regular PEM files'
        )
    _validate_cert_pair(cert_path, key_path)
    return cert_path, key_path


def get_cert():
    cert_path, key_path = _get_mounted_cert()
    if cert_path and key_path:
        logger.info('TLS certificate source: mounted files')
        return cert_path, key_path

    logger.info('Mounted TLS pair unavailable; trying Vault AppRole')
    try:
        secret = _get_secret()
        portal_chain = secret['portal_chain']
        portal_key = secret['portal_key']

        cert_dir = _get_cert_dir()
        cert_path = os.path.join(cert_dir, 'portal.crt')
        key_path = os.path.join(cert_dir, 'portal.key')

        with open(cert_path, 'w', encoding='utf-8') as f:
            f.write(portal_chain)
        with open(key_path, 'w', encoding='utf-8') as f:
            f.write(portal_key)

        _validate_cert_pair(cert_path, key_path)
        logger.info('TLS certificate source: Vault AppRole')
        return cert_path, key_path
    except Exception:
        logger.warning('Vault TLS certificate unavailable; falling back to HTTP on port 5093')
        return None, None


def _get_secret():
    tenant = os.environ.get('VAULT_TENANT')
    url_secman = os.environ.get('VAULT_ADDR')
    path_secman_secret = os.environ.get('VAULT_KV_PATH')
    role_id = os.environ.get('ROLE_ID')
    secret_id = os.environ.get('SECRET_ID')

    client_token = get_token_by_approle(url_secman, tenant, role_id=role_id, secret_id=secret_id)
    return get_secret(url_secman, tenant, client_token, path_secman_secret)


def get_token_by_approle(url, tenant, role_id, secret_id):
    headers = {
        'Content-Type': 'application/json',
        'x-vault-namespace': tenant,
    }
    data = {
        'role_id': role_id,
        'secret_id': secret_id,
    }
    response = requests.post(f'{url}/v1/auth/approle/login', headers=headers, json=data, verify=False, timeout=10)
    if response.status_code != 200:
        raise requests.ConnectionError('Vault AppRole authentication failed')
    return json_load(response.content)['auth']['client_token']


def get_secret(url, tenant, token, path):
    headers = {
        'Content-Type': 'application/json',
        'x-vault-namespace': tenant,
        'x-vault-token': token,
    }
    response = requests.get(f'{url}/v1/{tenant}/{path}', headers=headers, verify=False, timeout=10)
    if response.status_code != 200:
        raise requests.ConnectionError('Vault certificate request failed')
    return json_load(response.content)['data']
