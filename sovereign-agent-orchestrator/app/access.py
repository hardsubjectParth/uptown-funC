"""Role-to-tier-database routing rules.

Three physically separate PostgreSQL + pgvector databases hold RAG content:
'admin', 'higher', and 'lower'. A role can only read the tiers it is
entitled to, so the local model is never handed context from a database a
lower-privileged user cannot themselves query.

Each document is written into exactly one tier database. Read access then
cascades downward: admin reads admin+higher+lower, higher reads
higher+lower, lower reads lower only. This means an 'everyone' upload only
needs to be written once, to the 'lower' database, to become visible to
every tier.

Upload scopes:
- admin: 'private' -> admin database only. 'everyone' -> lower database
  (visible to lower, higher, and admin).
- higher: 'restricted' -> higher database (visible to higher and admin
  only). 'everyone' -> lower database (visible to lower, higher, and
  admin).
- lower: always the lower database; lower has no scope choice.
"""
from enum import StrEnum
from fastapi import HTTPException


class Role(StrEnum):
    ADMIN = 'admin'
    HIGHER = 'higher'
    LOWER = 'lower'


READABLE_TIERS = {
    Role.ADMIN: ('admin', 'higher', 'lower'),
    Role.HIGHER: ('higher', 'lower'),
    Role.LOWER: ('lower',),
}

UPLOAD_SCOPES = {
    Role.ADMIN: {'private': 'admin', 'everyone': 'lower'},
    Role.HIGHER: {'restricted': 'higher', 'everyone': 'lower'},
    Role.LOWER: {'private': 'lower'},
}

DEFAULT_SCOPE = {Role.ADMIN: 'private', Role.HIGHER: 'restricted', Role.LOWER: 'private'}


def readable_tiers(role: str) -> tuple[str, ...]:
    try:
        return READABLE_TIERS[Role(role)]
    except ValueError as exc:
        raise HTTPException(403, 'ROLE_NOT_AUTHORIZED') from exc


def allowed_scopes(role: str) -> list[str]:
    try:
        return sorted(UPLOAD_SCOPES[Role(role)].keys())
    except ValueError as exc:
        raise HTTPException(403, 'ROLE_NOT_AUTHORIZED') from exc


def resolve_upload_tier(role: str, scope: str | None) -> str:
    try:
        options = UPLOAD_SCOPES[Role(role)]
    except ValueError as exc:
        raise HTTPException(403, 'ROLE_NOT_AUTHORIZED') from exc
    scope = scope or DEFAULT_SCOPE[Role(role)]
    if scope not in options:
        raise HTTPException(422, 'INVALID_SHARING_SCOPE')
    return options[scope]
