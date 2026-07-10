import atexit
import os
import shutil
import tempfile
from json import loads as json_load

import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CERT_DIR = None


def _get_cert_dir():
    global _CERT_DIR
    if _CERT_DIR is None:
        _CERT_DIR = tempfile.mkdtemp(prefix='app_certs_')
        atexit.register(shutil.rmtree, _CERT_DIR, ignore_errors=True)
    return _CERT_DIR


def get_cert():
    try:
        portal_chain = _get_info('portal_chain')
        portal_key = _get_info('portal_key')

        cert_dir = _get_cert_dir()
        cert_path = os.path.join(cert_dir, 'portal.crt')
        key_path = os.path.join(cert_dir, 'portal.key')

        with open(cert_path, 'w') as f:
            f.write(portal_chain)
        with open(key_path, 'w') as f:
            f.write(portal_key)

        return cert_path, key_path
    except Exception as err:
        print(err)
        return None, None


def _get_info(info):
    tenant = os.environ.get('VAULT_TENANT')
    url_secman = os.environ.get('VAULT_ADDR')
    path_secman_secret = os.environ.get('VAULT_KV_PATH')
    role_id = os.environ.get('ROLE_ID')
    secret_id = os.environ.get('SECRET_ID')

    client_token = get_token_by_approle(url_secman, tenant, role_id=role_id, secret_id=secret_id)
    cred = get_secret(url_secman, tenant, client_token, path_secman_secret)
    return cred[info]


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
        raise requests.ConnectionError(f'response code: {response.status_code}\ncontent: {response.content}')
    return json_load(response.content)['auth']['client_token']


def get_secret(url, tenant, token, path):
    headers = {
        'Content-Type': 'application/json',
        'x-vault-namespace': tenant,
        'x-vault-token': token,
    }
    response = requests.get(f'{url}/v1/{tenant}/{path}', headers=headers, verify=False, timeout=10)
    if response.status_code != 200:
        return f'[HTTP ERROR] path: {path}; response code: {response.status_code}; content: {response.content}'
    return json_load(response.content)['data']


load_dotenv()
