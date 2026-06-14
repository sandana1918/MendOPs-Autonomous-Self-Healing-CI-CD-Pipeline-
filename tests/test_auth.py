import pytest
from fastapi import HTTPException

from app.auth import _extract_bearer_token, _has_role


def test_extract_bearer_token():
    assert _extract_bearer_token("Bearer abc.def") == "abc.def"


def test_extract_bearer_token_rejects_missing_header():
    with pytest.raises(HTTPException) as exc:
        _extract_bearer_token(None)
    assert exc.value.status_code == 401


def test_has_role_from_realm_access():
    claims = {"realm_access": {"roles": ["patchforge-ci"]}}
    assert _has_role(claims, "patchforge-ci")


def test_has_role_from_resource_access():
    claims = {"resource_access": {"patchforge-api": {"roles": ["patchforge-ci"]}}}
    assert _has_role(claims, "patchforge-ci")
