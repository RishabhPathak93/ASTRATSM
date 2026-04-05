"""
chat/middleware.py
JWT authentication middleware for Django Channels WebSocket connections.

The frontend must send the token in the WebSocket URL query string:
  ws://host/ws/chat/1/?token=<access_token>

This is necessary because browsers cannot set custom headers on WebSocket
connections.
"""
import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('nexus')


@database_sync_to_async
def get_user_from_token(token: str):
    """Validate a JWT access token and return the corresponding User or AnonymousUser."""
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
        from accounts.models import User

        validated = AccessToken(token)
        user_id   = validated.get('user_id')
        if not user_id:
            return AnonymousUser()
        user = User.objects.get(pk=user_id, is_active=True)
        return user
    except Exception as exc:
        logger.debug('WS JWT auth failed: %s', exc)
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    ASGI middleware that authenticates WebSocket connections via a JWT
    token passed as a query parameter: ?token=<access_token>
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            query_string = scope.get('query_string', b'').decode()
            params       = parse_qs(query_string)
            token_list   = params.get('token', [])
            if token_list:
                scope['user'] = await get_user_from_token(token_list[0])
            else:
                scope['user'] = AnonymousUser()
        return await self.inner(scope, receive, send)
