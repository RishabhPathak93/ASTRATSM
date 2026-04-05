# Nexus CRM — Frontend

React + Vite frontend for the Nexus CRM backend.

## Stack

- **React 18** with hooks
- **Vite 5** for bundling & dev server
- **React Router v6** for routing
- **TanStack Query v5** for server state & caching
- **Zustand** for auth state
- **Recharts** for dashboard charts
- **Lucide React** for icons
- **Axios** with JWT interceptors & auto-refresh

## Design

- Dark-first industrial aesthetic
- Fonts: **Syne** (display/headings) + **DM Sans** (body) + **DM Mono** (data/code)
- Accent: acid yellow `#e8ff47`
- CSS custom properties for full design-system consistency

## Getting started

```bash
# Install dependencies
npm install

# Start dev server (proxies /api → http://localhost:8000 and /ws → ws://localhost:8000)
npm run dev

# Build for production
npm run build
```

## Environment

The dev server is pre-configured in `vite.config.js` to proxy:
- `/api/**` → `http://localhost:8000` (Django backend)
- `/ws/**` → `ws://localhost:8000` (WebSocket/Daphne)

In production, configure your reverse proxy (Nginx) to serve the built assets and proxy API/WS traffic to the backend.

## Pages & Features

| Route | Description |
|-------|-------------|
| `/login` | JWT login with rate-limit awareness |
| `/dashboard` | Stats, area chart, pie chart, recent projects |
| `/clients` | Client table with status filter, create modal |
| `/projects` | Project grid with filter by status/priority |
| `/projects/:id` | Detail: metrics, updates, documents, team |
| `/timelines` | Gantt visualization + milestone tracking |
| `/resources` | Team member list |
| `/chat` | Real-time WebSocket chat with room list |
| `/notifications` | Notification list with read/clear actions |
| `/profile` | Edit profile + change password |
| `/settings` | Admin: user management + role permissions |

## Architecture

```
src/
├── api/          # Axios client + per-domain API helpers
├── components/
│   ├── layout/   # AppLayout, Sidebar, Topbar
│   └── ui/       # Button, Badge, Modal, Table, etc.
├── pages/        # Route-level page components
├── stores/       # Zustand auth store
└── utils/        # Date, currency, status helpers
```

## Auth flow

1. POST `/api/v1/auth/login/` → receives `{ access, refresh, user }`
2. Tokens stored in `localStorage`
3. Axios request interceptor attaches `Authorization: Bearer <access>`
4. On 401, response interceptor refreshes automatically via `/api/v1/auth/token/refresh/`
5. On refresh failure → logout + redirect to `/login`
