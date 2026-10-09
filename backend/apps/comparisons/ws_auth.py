from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.users.authentication import TrackingJWTAuthentication


@database_sync_to_async
def _user_from_token(raw_token: str | None):
    if not raw_token:
        return AnonymousUser()
    auth = TrackingJWTAuthentication()
    try:
        return auth.get_user(auth.get_validated_token(raw_token))
    except (InvalidToken, TokenError, AuthenticationFailed):
        return AnonymousUser()


class JWTQueryAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        scope = dict(scope)
        scope["user"] = await _user_from_token((query.get("token") or [None])[0])
        return await super().__call__(scope, receive, send)
