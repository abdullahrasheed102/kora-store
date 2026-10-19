"""Password hashing with argon2. Used by the seed (admin user) and by login in phase 3."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# argon2id with the library's recommended settings. It is deliberately slow and uses a lot of
# memory, so an attacker who steals the hashes can only try a few guesses per second.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    # The salt (random bytes) and settings are stored inside the hash string itself.
    return _hasher.hash(password)


def password_needs_rehash(password_hash: str) -> bool:
    """True if the hash was made with older/weaker settings than the current ones."""
    return _hasher.check_needs_rehash(password_hash)


# Used when a login names an email that doesn't exist: we still run one full verify, so
# "no such user" takes as long as "wrong password" and timing doesn't reveal which emails exist.
DUMMY_PASSWORD_HASH = _hasher.hash("not-a-real-password")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
