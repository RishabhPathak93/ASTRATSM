# UAT Setup

## Backend
- Create a Python virtual environment inside `backend` and install `requirements.txt`.
- Create `backend/.env` from `backend/.env.uat.example`.
- Run `python manage.py migrate`.
- Run `python manage.py create_admin` or `python manage.py createsuperuser`.
- Serve Django with `gunicorn nexus.wsgi:application` on Linux or `daphne nexus.asgi:application` if you need websocket traffic handled directly.
- Put Nginx in front of Django and route `/api/`, `/admin/`, `/media/`, and websocket traffic to the backend.

## Frontend
- In `frontend`, install dependencies with `npm install`.
- Build with `npm run build`.
- Serve `frontend/dist` from Nginx or any static server.
- Proxy `/api/` requests to the Django backend.

## Required infra
- PostgreSQL database
- Redis for cache and channels
- HTTPS certificate for the UAT hostname

## Admin access
- `/admin` is provided by Django.
- Users with role `admin` are automatically marked as Django staff by the app changes in this branch.

## Recommended UAT checks
- Login as admin, manager, and resource.
- Verify managers only see their assigned resources.
- Verify admin can create, edit, delete, and export resources.
- Verify Excel exports for clients, projects, and resources.
- Verify Django admin at `/admin` only works for admin users.
