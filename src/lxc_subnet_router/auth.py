from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def can(config: dict, group: str, permission: str) -> bool:
    permissions = config.get("groups", {}).get(group, {}).get("permissions", [])
    return permission in permissions
