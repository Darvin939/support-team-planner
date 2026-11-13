import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from backend import ssl_context as tls
from tls_test_support import create_test_pair


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def cert_pair(tmp_path_factory):
    return create_test_pair(tmp_path_factory.mktemp('tls pair '))


@pytest.fixture(autouse=True)
def isolated_tls(monkeypatch, tmp_path):
    for name in ('SUPPORT_PLANNER_TLS_CERT_FILE', 'SUPPORT_PLANNER_TLS_KEY_FILE',
                 'VAULT_ADDR', 'VAULT_TENANT', 'VAULT_KV_PATH', 'ROLE_ID', 'SECRET_ID'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(tls, '_CERT_DIR', None)
    # Any unexpected real network request fails at the transport boundary.
    monkeypatch.setattr(tls.requests, 'post', Mock(side_effect=AssertionError('Unexpected Vault POST')))
    monkeypatch.setattr(tls.requests, 'get', Mock(side_effect=AssertionError('Unexpected Vault GET')))


def set_paths(monkeypatch, cert, key):
    monkeypatch.setenv('SUPPORT_PLANNER_TLS_CERT_FILE', str(cert))
    monkeypatch.setenv('SUPPORT_PLANNER_TLS_KEY_FILE', str(key))


def test_mounted_pair_is_used_directly_without_vault_or_copy(monkeypatch, cert_pair):
    cert, key = cert_pair
    set_paths(monkeypatch, cert, key)
    with patch.object(tls, '_get_secret') as secret, patch.object(tls, '_get_cert_dir') as directory:
        assert tls.get_cert() == (str(cert), str(key))
    secret.assert_not_called()
    directory.assert_not_called()
    assert cert.is_file() and key.is_file()


@pytest.mark.parametrize('kind', ['unset', 'empty', 'cert-only', 'key-only', 'missing-cert', 'missing-key'])
def test_absent_pair_tries_legacy_vault(monkeypatch, tmp_path, cert_pair, kind):
    cert, key = cert_pair
    if kind == 'empty':
        set_paths(monkeypatch, '', '')
    elif kind == 'cert-only':
        monkeypatch.setenv('SUPPORT_PLANNER_TLS_CERT_FILE', str(cert))
    elif kind == 'key-only':
        monkeypatch.setenv('SUPPORT_PLANNER_TLS_KEY_FILE', str(key))
    elif kind == 'missing-cert':
        set_paths(monkeypatch, tmp_path / 'missing', key)
    elif kind == 'missing-key':
        set_paths(monkeypatch, cert, tmp_path / 'missing')
    with patch.object(tls, '_get_secret', side_effect=RuntimeError('not-for-logs')) as secret:
        assert tls.get_cert() == (None, None)
    secret.assert_called_once_with()


@pytest.mark.parametrize('kind', ['invalid-cert', 'invalid-key', 'mismatch', 'directory', 'unreadable', 'stat-denied'])
def test_found_invalid_pair_stops_without_fallback(monkeypatch, tmp_path, cert_pair, caplog, kind):
    cert, key = cert_pair
    if kind.startswith('invalid'):
        invalid = tmp_path / 'invalid.pem'
        invalid.write_text('sensitive-pem-content', encoding='utf-8')
        cert, key = (invalid, key) if kind == 'invalid-cert' else (cert, invalid)
    elif kind == 'mismatch':
        _, key = create_test_pair(tmp_path / 'other')
    elif kind == 'directory':
        key = tmp_path
    elif kind == 'unreadable':
        # Deterministic for root runners as well as unprivileged users.
        monkeypatch.setattr(tls.ssl.SSLContext, 'load_cert_chain', Mock(side_effect=PermissionError('sensitive-pem-content')))
    set_paths(monkeypatch, cert, key)
    stat_patch = patch.object(tls.os, 'stat', side_effect=PermissionError('sensitive-pem-content')) if kind == 'stat-denied' else nullcontext()
    with stat_patch, patch.object(tls, '_get_secret') as secret:
        with pytest.raises(tls.TLSConfigurationError) as error:
            tls.get_cert()
    secret.assert_not_called()
    rendered = ''.join(traceback.format_exception(type(error.value), error.value, error.tb))
    assert 'sensitive-pem-content' not in rendered + caplog.text


def test_encrypted_mounted_key_never_prompts(monkeypatch, tmp_path, cert_pair):
    cert, key = cert_pair
    encrypted = tmp_path / 'encrypted.key'
    subprocess.run(
        ['openssl', 'pkey', '-in', str(key), '-aes-256-cbc', '-passout', 'stdin', '-out', str(encrypted)],
        input='test-only-passphrase\n', text=True, encoding='utf-8', capture_output=True,
        check=True, timeout=10, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'),
    )
    env = dict(os.environ, SUPPORT_PLANNER_SKIP_DOTENV='1',
               SUPPORT_PLANNER_TLS_CERT_FILE=str(cert), SUPPORT_PLANNER_TLS_KEY_FILE=str(encrypted))
    result = subprocess.run(
        [sys.executable, '-c', 'from backend.ssl_context import get_cert; get_cert()'],
        cwd=ROOT, env=env, input='', capture_output=True, text=True, encoding='utf-8', timeout=5,
    )
    assert result.returncode != 0
    assert 'TLSConfigurationError' in result.stderr
    assert 'Enter PEM pass phrase' not in result.stderr


def test_external_dotenv_paths_are_loaded_before_certificate_selection(tmp_path, cert_pair):
    cert, key = cert_pair
    selected = tmp_path / 'env'
    selected.write_text('SUPPORT_PLANNER_TLS_CERT_FILE=%s\nSUPPORT_PLANNER_TLS_KEY_FILE=%s\n' % (cert, key), encoding='utf-8')
    env = os.environ.copy()
    for name in ('SUPPORT_PLANNER_SKIP_DOTENV', 'SUPPORT_PLANNER_TLS_CERT_FILE', 'SUPPORT_PLANNER_TLS_KEY_FILE'):
        env.pop(name, None)
    env.update(SUPPORT_PLANNER_ENV_FILE=str(selected), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    result = subprocess.run(
        [sys.executable, '-c', 'import json; from backend.ssl_context import get_cert; print(json.dumps(get_cert()))'],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=5, check=True,
    )
    assert json.loads(result.stdout) == [str(cert), str(key)]


def test_legacy_requests_fields_and_temporary_cleanup(monkeypatch, cert_pair, tmp_path, caplog):
    cert, key = cert_pair
    secret = {'portal_chain': cert.read_text(encoding='utf-8'), 'portal_key': key.read_text(encoding='utf-8')}
    credentials = dict(VAULT_ADDR='https://vault.fixture', VAULT_TENANT='fixture-tenant',
                       VAULT_KV_PATH='secret/portal', ROLE_ID='fixture-role', SECRET_ID='fixture-secret')
    for name, value in credentials.items():
        monkeypatch.setenv(name, value)
    tls.requests.post.return_value = Mock(status_code=200, content=json.dumps({'auth': {'client_token': 'fixture-token'}}).encode())
    tls.requests.post.side_effect = None
    tls.requests.get.return_value = Mock(status_code=200, content=json.dumps({'data': secret}).encode())
    tls.requests.get.side_effect = None
    directory = tmp_path / 'legacy'
    directory.mkdir()
    with patch.object(tls.tempfile, 'mkdtemp', return_value=str(directory)), patch.object(tls.atexit, 'register') as cleanup:
        with caplog.at_level(logging.INFO, logger=tls.__name__):
            result = tls.get_cert()
    assert result == (str(directory / 'portal.crt'), str(directory / 'portal.key'))
    assert Path(result[0]).read_text(encoding='utf-8') == secret['portal_chain']
    assert Path(result[1]).read_text(encoding='utf-8') == secret['portal_key']
    tls.requests.post.assert_called_once_with(
        'https://vault.fixture/v1/auth/approle/login',
        headers={'Content-Type': 'application/json', 'x-vault-namespace': 'fixture-tenant'},
        json={'role_id': 'fixture-role', 'secret_id': 'fixture-secret'}, verify=False, timeout=10,
    )
    tls.requests.get.assert_called_once_with(
        'https://vault.fixture/v1/fixture-tenant/secret/portal',
        headers={'Content-Type': 'application/json', 'x-vault-namespace': 'fixture-tenant', 'x-vault-token': 'fixture-token'},
        verify=False, timeout=10,
    )
    cleanup.assert_called_once_with(shutil.rmtree, str(directory), ignore_errors=True)
    assert 'Vault AppRole' in caplog.text
    assert 'fixture-token' not in caplog.text and secret['portal_key'] not in caplog.text
    callback, path = cleanup.call_args.args
    callback(path, **cleanup.call_args.kwargs)
    assert not directory.exists()


@pytest.mark.parametrize('kind', ['auth', 'read', 'json', 'fields', 'write', 'pem'])
def test_legacy_failure_returns_no_pair_without_exposing_secrets(monkeypatch, tmp_path, cert_pair, caplog, capsys, kind):
    cert, key = cert_pair
    secret_text = 'private-key-or-token-not-for-logs'
    secret = {'portal_chain': cert.read_text(encoding='utf-8'), 'portal_key': key.read_text(encoding='utf-8')}
    if kind in ('auth', 'read', 'json'):
        tls.requests.post.side_effect = None
        tls.requests.post.return_value = Mock(status_code=200, content=b'{"auth":{"client_token":"fixture-token"}}')
        tls.requests.get.side_effect = None
        tls.requests.get.return_value = Mock(status_code=200, content=json.dumps({'data': secret}).encode())
        response = tls.requests.post.return_value if kind == 'auth' else tls.requests.get.return_value
        response.status_code = 403 if kind != 'json' else 200
        response.content = secret_text.encode()
    else:
        if kind == 'fields':
            secret = {'unexpected-field': secret_text}
        elif kind == 'pem':
            secret['portal_key'] = secret_text
        monkeypatch.setattr(tls, '_get_secret', Mock(return_value=secret))
        monkeypatch.setattr(tls, '_get_cert_dir', Mock(return_value=str(tmp_path)))
        if kind == 'write':
            monkeypatch.setattr('builtins.open', Mock(side_effect=PermissionError(secret_text)))
    assert tls.get_cert() == (None, None)
    out = capsys.readouterr()
    assert 'falling back to HTTP' in caplog.text
    assert secret_text not in caplog.text + out.out + out.err
    assert 'fixture-token' not in caplog.text + out.out + out.err


@pytest.mark.parametrize('mode', ['https', 'http', 'invalid-mounted'])
def test_main_selects_transport_and_stops_on_mounted_error(monkeypatch, cert_pair, caplog, mode):
    from backend import application
    cert, key = cert_pair
    with patch('uvicorn.run') as run:
        if mode == 'invalid-mounted':
            with patch.object(application, 'get_cert', side_effect=tls.TLSConfigurationError('Invalid TLS pair')):
                with pytest.raises(tls.TLSConfigurationError):
                    application.main()
            run.assert_not_called()
            return
        pair = (str(cert), str(key)) if mode == 'https' else (None, None)
        with patch.object(application, 'get_cert', return_value=pair):
            with caplog.at_level(logging.INFO, logger=application.__name__):
                application.main()
        kwargs = dict(port=5093, host='0.0.0.0', log_config=None)
        if mode == 'https':
            kwargs.update(ssl_keyfile=str(key), ssl_certfile=str(cert))
        run.assert_called_once_with(application.app, **kwargs)
    assert 'Starting %s' % mode.upper() in caplog.text
