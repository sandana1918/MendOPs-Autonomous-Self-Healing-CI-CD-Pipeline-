from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.config import settings


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
    return token


async def verify_keycloak_identity(request: Request) -> dict[str, Any]:
    if not settings.KEYCLOAK_ENABLED:
        return {"enabled": False}

    token = _extract_bearer_token(request.headers.get("Authorization"))
    jwks_url = settings.KEYCLOAK_JWKS_URL or _default_jwks_url()

    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_AUDIENCE,
            issuer=settings.KEYCLOAK_ISSUER_URL.rstrip("/"),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"identity verification failed: {exc}",
        ) from exc

    if settings.KEYCLOAK_REQUIRED_ROLE and not _has_role(claims, settings.KEYCLOAK_REQUIRED_ROLE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing required role")

    return claims


def _default_jwks_url() -> str:
    issuer = settings.KEYCLOAK_ISSUER_URL.rstrip("/")
    if not issuer:
        raise HTTPException(status_code=500, detail="KEYCLOAK_ISSUER_URL missing")
    return f"{issuer}/protocol/openid-connect/certs"


def _has_role(claims: dict[str, Any], role: str) -> bool:
    realm_roles = claims.get("realm_access", {}).get("roles", [])
    resource_roles = []
    for client in claims.get("resource_access", {}).values():
        resource_roles.extend(client.get("roles", []))
    return role in realm_roles or role in resource_roles
