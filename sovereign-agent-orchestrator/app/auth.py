import os
from functools import lru_cache
from fastapi import Header, HTTPException
import jwt
from jwt import PyJWKClient


@lru_cache(maxsize=1)
def _jwks_client(url):
    return PyJWKClient(url)


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
    roles = claims.get('roles', claims.get('role', 'user'))
    role = roles[0] if isinstance(roles, list) and roles else roles
    return {
        'user_id': claims['sub'],
        'role': role,
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
        'role': x_user_role or os.getenv('API_ROLE', 'user'),
        'tenant_id': x_tenant_id or os.getenv('DEFAULT_TENANT_ID', 'default'),
        'clearance': x_clearance or os.getenv('DEFAULT_CLEARANCE', 'internal'),
    }