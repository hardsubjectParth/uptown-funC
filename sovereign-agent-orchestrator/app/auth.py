import os
from functools import lru_cache
from fastapi import Header, HTTPException
import jwt
from jwt import PyJWKClient

from app.access import Role


@lru_cache(maxsize=1)
def _jwks_client(url):
    return PyJWKClient(url)


# Highest privilege first: an identity provider that emits several roles resolves to the
# most privileged tier role it actually carries, and anything unrecognised (or missing)
# falls back to the least privileged tier rather than to an invalid role.
_ROLE_PRECEDENCE = (Role.ADMIN, Role.HIGHER, Role.LOWER)


def _resolve_role(claim) -> str:
    values = claim if isinstance(claim, (list, tuple, set)) else [claim]
    names = {str(value).strip().lower() for value in values if value}
    return next((role.value for role in _ROLE_PRECEDENCE if role.value in names), Role.LOWER.value)


def _jwt_identity(token):
    issuer = os.getenv('OIDC_ISSUER', '').strip() or None
    audience = os.getenv('OIDC_AUDIENCE', '').strip() or None
    public_key = os.getenv('JWT_PUBLIC_KEY', '').replace('\\n', '\n').strip()
    jwks_url = os.getenv('OIDC_JWKS_URL', '').strip()
    try:
        if jwks_url:
            key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            algorithms = ['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512']
        elif public_key:
            key = public_key
            algorithms = ['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512']
        else:
            secret = os.getenv('JWT_SECRET', '').strip()
            if not secret:
                raise ValueError('JWT verification key is not configured')
            key = secret
            algorithms = ['HS256']
        claims = jwt.decode(token, key, algorithms=algorithms, audience=audience, issuer=issuer, options={'require': ['sub', 'exp']})
    except Exception as exc:
        raise HTTPException(401, 'INVALID_TOKEN') from exc
    return {
        'user_id': claims['sub'],
        'role': _resolve_role(claims.get('roles', claims.get('role'))),
        'tenant_id': claims.get('tenant_id', claims.get('tenant', 'default')),
        'clearance': claims.get('clearance', 'internal'),
        'claims': claims,
    }


def current_identity(authorization: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), x_user_id: str | None = Header(default=None), x_user_role: str | None = Header(default=None), x_clearance: str | None = Header(default=None)):
    scheme, _, token = (authorization or '').partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise HTTPException(401, 'AUTHENTICATION_REQUIRED')
    if os.getenv('AUTH_MODE', 'jwt').lower() != 'api_key':
        return _jwt_identity(token)
    expected = os.getenv('API_KEY', '').strip()
    if not expected or token != expected:
        raise HTTPException(401, 'AUTHENTICATION_REQUIRED')
    return {
        'user_id': x_user_id or os.getenv('API_USER_ID', 'api-user'),
        'role': _resolve_role(x_user_role or os.getenv('API_ROLE')),
        'tenant_id': x_tenant_id or os.getenv('DEFAULT_TENANT_ID', 'default'),
        'clearance': x_clearance or os.getenv('DEFAULT_CLEARANCE', 'internal'),
    }
