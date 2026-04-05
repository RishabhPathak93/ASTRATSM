"""
Run once to fix existing chat rooms:
  python manage.py fix_chat_rooms
"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Add all admins/managers to all existing project chat rooms'

    def handle(self, *args, **kwargs):
        from chat.models import ChatRoom
        from accounts.models import User

        staff = list(User.objects.filter(role__in=['admin', 'manager'], is_active=True))
        rooms = ChatRoom.objects.prefetch_related('project__resources').all()
        count = 0
        for room in rooms:
            # Add all admins + managers
            room.members.add(*staff)
            # Add all project resources
            if room.project:
                for user in room.project.resources.filter(is_active=True):
                    room.members.add(user)
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Fixed {count} rooms. Added {len(staff)} staff members to all rooms.'
        ))