import os
from fastapi import Header, HTTPException


def current_identity(authorization: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    expected = os.getenv('API_KEY', '').strip()
    if expected and authorization != f'Bearer {expected}':
        raise HTTPException(401, 'AUTHENTICATION_REQUIRED')
    return {'user_id': os.getenv('API_USER_ID', 'api-user'), 'role': os.getenv('API_ROLE', 'user'), 'tenant_id': x_tenant_id or os.getenv('DEFAULT_TENANT_ID', 'default'), 'clearance': os.getenv('DEFAULT_CLEARANCE', 'internal')}