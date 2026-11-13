"""Generate short-lived loopback certificates using OpenSSL, only for tests."""
import os
import subprocess
from pathlib import Path


def create_test_pair(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / 'openssl.cnf'
    config.write_text(
        '[req]\nprompt = no\ndistinguished_name = dn\nx509_extensions = extensions\n'
        '[dn]\nCN = localhost\n'
        '[extensions]\nsubjectAltName = DNS:localhost,IP:127.0.0.1\n'
        'basicConstraints = critical,CA:TRUE\nkeyUsage = critical,digitalSignature,keyEncipherment,keyCertSign\n'
        'extendedKeyUsage = serverAuth\n', encoding='utf-8',
    )
    cert, key = directory / 'tls.crt', directory / 'tls.key'
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
         '-keyout', str(key), '-out', str(cert), '-config', str(config)],
        env=env, check=True, capture_output=True, timeout=20,
    )
    key.chmod(0o600)
    return cert, key
