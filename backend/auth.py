import hashlib
import hmac
import secrets

_ALGORITHM = 'sha256'
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """Хэширует пароль (PBKDF2-HMAC-SHA256), возвращает самоописывающуюся строку вида
    'pbkdf2_sha256$<iterations>$<salt>$<hash>'."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode('utf-8'), bytes.fromhex(salt), _ITERATIONS)
    return f'pbkdf2_sha256${_ITERATIONS}${salt}${dk.hex()}'


def verify_password(password: str, password_hash: str) -> bool:
    """Сверяет пароль с хэшем, сформированным hash_password()."""
    if not password_hash:
        return False
    try:
        algo, iterations, salt, hash_hex = password_hash.split('$')
        iterations = int(iterations)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode('utf-8'), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(dk.hex(), hash_hex)
