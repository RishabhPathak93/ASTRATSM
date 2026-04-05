# Nexus CRM — Production Backend

A production-grade Django REST Framework backend with zero dummy data,
full JWT authentication, WebSocket chat, role-based access control,
and comprehensive input validation.

---

## What changed from the previous version

| Area | Change |
|------|--------|
| **Dummy data** | Completely removed. No seed_data command, no hardcoded users. |
| **Secrets** | `SECRET_KEY` has no fallback default — server won't start without it set. |
| **Database** | PostgreSQL required — SQLite removed from settings entirely. |
| **Passwords** | Django's full password validation pipeline (length, common, numeric, similarity). |
| **JWT WebSocket** | Custom `JWTAuthMiddleware` reads token from `?token=` query param — no `AuthMiddlewareStack` dependency. |
| **Chat signals** | `ChatRoom` auto-created when a `Project` is created; members synced via M2M signal. |
| **Role permissions** | `RolePermission` rows auto-created via `post_migrate` signal — no admin intervention needed. |
| **Notifications** | Switched to `bulk_create` — one DB round-trip per event instead of N. |
| **Logging** | Structured logging with rotating file handlers; security events logged separately. |
| **Error responses** | Uniform `{status, code, message, errors}` shape via custom exception handler. |
| **Admin** | `seed_data` removed; `create_admin` command replaces it for first-run setup. |
| **Rate limiting** | Login endpoint throttled at 10/min; global 300/min for authenticated users. |
| **File validation** | Extension allowlist + size limits enforced on upload, avatar, and attachment endpoints. |
| **Sentry** | Integrated — enable by setting `SENTRY_DSN` in environment. |

---

## Project structure

```
nexus_prod/
├── manage.py
├── requirements.txt
├── .env.example
│
├── nexus/
│   ├── settings.py          # All config from env vars; no insecure defaults
│   ├── urls.py
│   ├── asgi.py              # WebSocket entry point with JWT middleware
│   ├── wsgi.py
│   ├── pagination.py        # StandardResultsPagination
│   └── exceptions.py        # Uniform error shape
│
├── accounts/                # Auth, users, role permissions
│   ├── models.py            # User (custom AbstractBaseUser), RolePermission
│   ├── serializers.py       # Full validation; password strength enforced
│   ├── views.py             # Login throttled; no self-delete/self-deactivate
│   ├── permissions.py       # IsAdmin, IsAdminOrManager, IsProjectMember, etc.
│   ├── middleware.py        # LastSeenMiddleware
│   ├── signals.py           # Auto-create RolePermission rows post-migrate
│   └── management/commands/create_admin.py   # First-run admin setup
│
├── clients/                 # Client onboarding
├── projects/                # Projects + documents + updates
├── timelines/               # Gantt phases + milestones
├── resources/               # Resource profiles + time entries
│
├── chat/
│   ├── models.py
│   ├── consumers.py         # Async WS consumer: message, edit, typing, read
│   ├── middleware.py        # JWT auth for WebSocket (?token=<jwt>)
│   ├── routing.py
│   ├── signals.py           # Auto-create room + sync members on project save
│   └── views.py             # REST fallback + message history
│
└── notifications/
    ├── models.py
    ├── utils.py             # bulk_create helper; exclude sender
    └── views.py
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in every value — especially SECRET_KEY, DB_*, REDIS_URL
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. Database

```bash
# Create the PostgreSQL database first, then:
python manage.py migrate
```

`RolePermission` rows are created automatically by a `post_migrate` signal.
No manual step required.

### 4. Create admin

```bash
python manage.py create_admin
# Prompts for email, name, password interactively
# Or use env vars: ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD
```

### 5. Run

```bash
# Development (HTTP + WebSocket combined)
python manage.py runserver

# Production (recommended)
# Serve HTTP with Gunicorn and WebSocket with Daphne behind Nginx
gunicorn nexus.wsgi:application --bind 0.0.0.0:8000 --workers 4
daphne nexus.asgi:application   --bind 0.0.0.0:8001
```

---

## API reference

### Auth
```
POST   /api/v1/auth/login/           → {access, refresh, user}
POST   /api/v1/auth/logout/          body: {refresh}
POST   /api/v1/auth/token/refresh/   body: {refresh}
GET    /api/v1/auth/me/
PATCH  /api/v1/auth/me/
POST   /api/v1/auth/change-password/
```

### User management (admin only for write)
```
GET    /api/v1/auth/users/
POST   /api/v1/auth/users/           (admin)
PATCH  /api/v1/auth/users/{id}/toggle_status/   (admin)
PATCH  /api/v1/auth/users/{id}/change_role/     (admin)
GET    /api/v1/auth/role-permissions/
PATCH  /api/v1/auth/role-permissions/{id}/      (admin/manager)
```

### Standard CRUD
```
/api/v1/clients/            GET, POST, GET/{id}, PUT/{id}, PATCH/{id}, DELETE/{id}
/api/v1/projects/           GET, POST, GET/{id}, …
  POST /{id}/add_update/
  POST /{id}/upload_document/
  PATCH/{id}/update_progress/
  POST /{id}/assign_resource/
  POST /{id}/remove_resource/
/api/v1/timelines/          GET, POST, …
  PATCH/{id}/update_progress/
  POST /{id}/add_milestone/
/api/v1/timelines/milestones/{id}/complete/
/api/v1/resources/          GET, POST, …
  PATCH/{id}/set_availability/
/api/v1/resources/time-entries/  GET, POST, …
  PATCH/{id}/approve/
/api/v1/notifications/      GET
  PATCH/{id}/mark_read/
  POST /mark_all_read/
  GET  /unread_count/
  DELETE /clear_all/
```

### Chat (REST)
```
GET  /api/v1/chat/rooms/
GET  /api/v1/chat/rooms/{id}/messages/?limit=50&before={msg_id}
POST /api/v1/chat/rooms/{id}/send_message/
POST /api/v1/chat/rooms/{id}/mark_read/
```

### Chat (WebSocket)
```
ws://host/ws/chat/{room_id}/?token=<access_token>
```

Send frames:
```json
{"action": "message", "text": "Hello team!"}
{"action": "typing",  "is_typing": true}
{"action": "read"}
{"action": "edit",    "message_id": 42, "text": "corrected text"}
```

Receive frames:
```json
{"type": "message",   "message_id":1, "text":"…", "sender_id":1, "sender_name":"…", "created_at":"…"}
{"type": "typing",    "user_id":2, "user_name":"…", "is_typing": true}
{"type": "user_join", "user_id":3, "user_name":"…"}
{"type": "edited",    "message_id":42, "text":"corrected text"}
{"type": "error",     "detail":"…"}
```

---

## Security hardening checklist

- [x] `SECRET_KEY` — no fallback, required from env
- [x] `DEBUG=False` in production
- [x] PostgreSQL required (no SQLite in production)
- [x] JWT token blacklisting on logout
- [x] Login endpoint rate-limited (10/min)
- [x] Password strength validators (min 8 chars, common, numeric)
- [x] File upload extension + size validation
- [x] WebSocket JWT authentication (`?token=`)
- [x] WebSocket membership check before accepting
- [x] HTTPS headers (`HSTS`, `Secure` cookies, SSL redirect)
- [x] `X_FRAME_OPTIONS = DENY`
- [x] CORS restricted to explicit origins
- [x] Sentry error tracking (optional)
- [x] No dummy/hardcoded users or passwords
- [ ] Run `python manage.py check --deploy` before going live
- [ ] Set up PostgreSQL with least-privilege user
- [ ] Configure Redis with AUTH password
- [ ] Use a reverse proxy (Nginx) for TLS termination
- [ ] Enable automated DB backups
