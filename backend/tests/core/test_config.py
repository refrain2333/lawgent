import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_env_example_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DEBUG=False,
            JWT_SECRET="change-me-to-a-random-secret",
        )
