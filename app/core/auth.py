import secrets
import bcrypt


def generate_api_key() -> tuple[str, str]:
    """Generate an API key. Returns (full_key, prefix)."""
    ulid = str(secrets.token_urlsafe(16))
    token = secrets.token_urlsafe(32)
    full_key = f"ak_{ulid}_{token}"
    prefix = full_key[:20]
    return full_key, prefix


def hash_key(key: str) -> str:
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def verify_key(key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(key.encode(), key_hash.encode())


def extract_prefix(key: str) -> str:
    return key[:20]
