# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Marzban is a censorship-resistant VPN management panel powered by Xray proxy core. It manages users, proxies, subscriptions, and distributed nodes through a unified web GUI. Current version: 0.8.4.

## Development Commands

### Running the Application
```bash
# Direct (requires Xray binary at /usr/local/bin/xray)
pip install -r requirements.txt
alembic upgrade head
python main.py

# Docker
docker compose up -d

# Debug mode (set DEBUG=True in .env first, enables auto-reload)
cd app/dashboard && npm install && cd ../..
python main.py
# Backend: localhost:8000, Frontend dev server: localhost:3000
```

### Database Migrations
```bash
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create new migration
```

### Building Frontend
```bash
bash build_dashboard.sh
# Or manually:
cd app/dashboard && npm install && VITE_BASE_API=/api/ npm run build -- --outDir build --assetsDir statics
```

### CLI Tool
```bash
python marzban-cli.py admin create   # Create sudo admin
python marzban-cli.py admin list     # List admins
python marzban-cli.py --help         # All commands
```

### Code Formatting
```bash
autopep8 <file> --max-line-length 120   # Python
# Frontend uses Prettier (config at app/dashboard/.prettierrc.json)
```

### Enable API Docs
Set `DOCS=True` in `.env` to expose `/openapi.json` and Swagger UI.

## Architecture

### Backend: FastAPI + SQLAlchemy + Xray gRPC

**Entry point**: `main.py` → `app/__init__.py` (FastAPI app factory). Single uvicorn worker only — APScheduler and Xray state are in-process singletons.

**Startup sequence**: uvicorn starts → FastAPI app created → CORS middleware added → routers/jobs/telegram/dashboard modules imported → scheduler starts → Xray core process launched → nodes connected.

### Key Modules

| Path | Purpose |
|------|---------|
| `config.py` | All configuration via python-decouple, reads `.env` |
| `app/routers/` | FastAPI route handlers (all under `/api/` prefix) |
| `app/db/models.py` | SQLAlchemy ORM models (User, Admin, Proxy, Node, etc.) |
| `app/db/crud.py` | All database operations (~45KB) |
| `app/models/` | Pydantic schemas for API request/response validation |
| `app/xray/core.py` | `XRayCore` — manages local Xray subprocess lifecycle |
| `app/xray/config.py` | `XRayConfig` — loads/modifies xray_config.json, injects user accounts |
| `app/xray/node.py` | `XRayNode` factory — auto-detects REST vs RPyC node protocol |
| `app/xray/operations.py` | Threaded user add/remove/update across core + all nodes |
| `xray_api/` | gRPC client for Xray management API (protobuf-based) |
| `app/jobs/` | APScheduler background jobs (prefix `0_` controls load order) |
| `app/subscription/` | Subscription format generators (V2Ray, Clash, SingBox, Outline) |
| `app/templates/` | Jinja2 templates for subscription configs (customizable via `CUSTOM_TEMPLATES_DIRECTORY`) |

### Frontend: React + TypeScript (Vite)

Lives in `app/dashboard/`. Built output goes to `app/dashboard/build/` and is served by FastAPI as static files. Uses Chakra UI, Zustand for state, React Query for data fetching.

### Node Connectivity

`XRayNode.__new__()` probes the remote node's TCP socket to auto-detect whether it speaks REST (newer marzban-node with uvicorn) or RPyC (legacy), returning the appropriate client class transparently.

### Xray User Management

Users are added/removed from running Xray inbounds via gRPC (no restart needed). The `xray_api/` package wraps compiled protobuf stubs. Supported protocols: VMess, VLESS, Trojan, Shadowsocks.

## Branch Strategy

- `master` — stable production releases
- `dev` — active development (current branch)
- Feature branches off `dev`

## Key Constraints

- **Single worker only**: `workers=1` in uvicorn — APScheduler and Xray module are not multi-worker safe.
- **No test suite**: There are no automated tests in the repository.
- **Without SSL certs**, uvicorn binds only to localhost. Use a reverse proxy (Nginx/Caddy) for production external access.
- DB models (SQLAlchemy) in `app/db/models.py` are separate from API models (Pydantic) in `app/models/`. Don't confuse them.
