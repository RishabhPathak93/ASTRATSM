"""accounts/middleware.py"""
from django.utils import timezone


class LastSeenMiddleware:
    """Update user.last_seen on every authenticated API request (throttled to once/5 min)."""
    INTERVAL_SECONDS = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._update_last_seen(request)
        return response

    @staticmethod
    def _update_last_seen(request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return
        last = user.last_seen
        now  = timezone.now()
        if last is None or (now - last).total_seconds() > LastSeenMiddleware.INTERVAL_SECONDS:
            user.touch()
