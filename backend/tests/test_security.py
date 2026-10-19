"""Password hashing."""

from app.security import hash_password, verify_password


def test_hash_is_not_the_password_and_verifies() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse battery")


def test_wrong_password_is_rejected() -> None:
    assert not verify_password(hash_password("correct horse battery"), "wrong")


def test_same_password_gives_different_hashes() -> None:
    # A random salt per hash: two users with the same password don't get the same hash.
    assert hash_password("same") != hash_password("same")


def test_garbage_hash_is_rejected_not_crashed() -> None:
    assert not verify_password("not-a-hash", "anything")
