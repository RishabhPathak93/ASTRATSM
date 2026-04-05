"""
chat/consumers.py
Production WebSocket consumer for project chat.

Protocol (JSON frames):
  Client → Server:
    {"action": "message", "text": "Hello!"}
    {"action": "typing",  "is_typing": true}
    {"action": "read"}
    {"action": "edit",    "message_id": 42, "text": "corrected"}

  Server → Client:
    {"type": "message",  "message_id":…, "text":…, "sender_id":…, "sender_name":…, "sender_initials":…, "created_at":…}
    {"type": "typing",   "user_id":…, "user_name":…, "is_typing":…}
    {"type": "user_join","user_id":…, "user_name":…}
    {"type": "user_leave","user_id":…, "user_name":…}
    {"type": "error",    "detail":…}
    {"type": "edited",   "message_id":…, "text":…}
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('nexus')

MAX_MESSAGE_LENGTH = 4000


class ChatConsumer(AsyncWebsocketConsumer):

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self):
        self.room_id    = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'chat_{self.room_id}'
        self.user       = self.scope.get('user')

        # Reject unauthenticated connections
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning('WS rejected: unauthenticated (room %s)', self.room_id)
            await self.close(code=4001)
            return

        # Reject if not a member
        if not await self.check_membership():
            logger.warning('WS rejected: user %s not a member of room %s', self.user.email, self.room_id)
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(self.room_group, {
            'type':      'user_join',
            'user_id':   self.user.id,
            'user_name': self.user.name,
        })
        logger.info('WS connected: user=%s room=%s', self.user.email, self.room_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
            if self.user and not isinstance(self.user, AnonymousUser):
                await self.channel_layer.group_send(self.room_group, {
                    'type':      'user_leave',
                    'user_id':   self.user.id,
                    'user_name': self.user.name,
                })

    async def receive(self, text_data):
        try:
            data   = json.loads(text_data)
            action = data.get('action', '').strip()
        except (json.JSONDecodeError, AttributeError):
            await self._send_error('Invalid JSON payload.')
            return

        handlers = {
            'message': self._handle_message,
            'typing':  self._handle_typing,
            'read':    self._handle_read,
            'edit':    self._handle_edit,
        }
        handler = handlers.get(action)
        if handler:
            await handler(data)
        else:
            await self._send_error(f'Unknown action: {action}')

    # ── Action handlers ───────────────────────────────────────────────────────

    async def _handle_message(self, data):
        text = data.get('text', '').strip()
        if not text:
            await self._send_error('Message text cannot be empty.')
            return
        if len(text) > MAX_MESSAGE_LENGTH:
            await self._send_error(f'Message too long (max {MAX_MESSAGE_LENGTH} chars).')
            return
        msg = await self.save_message(text)
        await self.channel_layer.group_send(self.room_group, {
            'type':             'chat_message',
            'message_id':       msg['id'],
            'text':             msg['text'],
            'sender_id':        msg['sender_id'],
            'sender_name':      msg['sender_name'],
            'sender_initials':  msg['sender_initials'],
            'created_at':       msg['created_at'],
        })

    async def _handle_typing(self, data):
        await self.channel_layer.group_send(self.room_group, {
            'type':      'typing_indicator',
            'user_id':   self.user.id,
            'user_name': self.user.name,
            'is_typing': bool(data.get('is_typing', False)),
        })

    async def _handle_read(self, _data):
        await self.mark_messages_read()

    async def _handle_edit(self, data):
        message_id = data.get('message_id')
        new_text   = data.get('text', '').strip()
        if not message_id or not new_text:
            await self._send_error('message_id and text are required for edit.')
            return
        success = await self.edit_message(message_id, new_text)
        if success:
            await self.channel_layer.group_send(self.room_group, {
                'type':       'message_edited',
                'message_id': message_id,
                'text':       new_text,
            })
        else:
            await self._send_error('Cannot edit this message.')

    # ── Group event dispatchers ───────────────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            **{k: v for k, v in event.items() if k != 'type'},
        }))

    async def typing_indicator(self, event):
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({'type': 'typing', **event}))

    async def user_join(self, event):
        await self.send(text_data=json.dumps({'type': 'user_join', **event}))

    async def user_leave(self, event):
        await self.send(text_data=json.dumps({'type': 'user_leave', **event}))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({'type': 'edited', **event}))

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def check_membership(self) -> bool:
        from .models import ChatRoom
        from accounts.models import User
        try:
            room = ChatRoom.objects.get(pk=self.room_id)
            return room.is_accessible_by(self.user)
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, text: str) -> dict:
        from .models import ChatRoom, Message
        room = ChatRoom.objects.get(pk=self.room_id)
        msg  = Message.objects.create(room=room, sender=self.user, text=text)
        return {
            'id':             msg.id,
            'text':           msg.text,
            'sender_id':      self.user.id,
            'sender_name':    self.user.name,
            'sender_initials': self.user.initials,
            'created_at':     msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def mark_messages_read(self):
        from .models import ChatRoom
        room   = ChatRoom.objects.get(pk=self.room_id)
        unread = room.messages.exclude(sender=self.user).exclude(read_by=self.user)
        for msg in unread:
            msg.read_by.add(self.user)

    @database_sync_to_async
    def edit_message(self, message_id: int, new_text: str) -> bool:
        from .models import Message
        try:
            msg = Message.objects.get(pk=message_id, sender=self.user)
            msg.text      = new_text
            msg.is_edited = True
            msg.save(update_fields=['text', 'is_edited', 'updated_at'])
            return True
        except Message.DoesNotExist:
            return False

    # ── Util ──────────────────────────────────────────────────────────────────

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({'type': 'error', 'detail': detail}))
