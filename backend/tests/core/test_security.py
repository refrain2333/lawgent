import bcrypt

from app.core.security import hash_password, needs_password_rehash, verify_password


def test_new_password_hash_supports_long_passwords_without_truncation():
    first = "a" * 72 + "first suffix"
    second = "a" * 72 + "different suffix"
    hashed = hash_password(first)

    assert verify_password(first, hashed)
    assert not verify_password(second, hashed)
    assert not needs_password_rehash(hashed)


def test_legacy_bcrypt_hash_remains_verifiable_and_is_marked_for_upgrade():
    password = "汉" * 25
    legacy_hash = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode("utf-8")

    assert verify_password(password, legacy_hash)
    assert needs_password_rehash(legacy_hash)
