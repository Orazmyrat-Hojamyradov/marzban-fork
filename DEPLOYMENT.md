# Deployment Guide

Step-by-step guide to deploy this Marzban fork with Xray xhttp inbound behind Bunny CDN.

## Architecture

```
Client (Happ/v2ray)
    │  HTTPS
    ▼
Bunny CDN  ←── pull zone origin: http://YOUR_SERVER_IP
    │  HTTP
    ▼
nginx :80  (proxy_buffering off — critical)
    │  HTTP
    ▼
Docker :2027  →  Xray xhttp inbound (VLESS-XHTTP-NOTLS)
Docker :8000  →  Marzban panel (management UI)
```

---

## Requirements

- Ubuntu 22.04 server
- Docker + Docker Compose
- A Bunny CDN pull zone pointing at this server

---

## 1. Clone the repo

```bash
cd /home/ubuntu
git clone https://github.com/Orazmyrat-Hojamyradov/marzban-fork.git
cd marzban-fork
```

---

## 2. Configure environment

```bash
cp .env.example .env   # or edit .env directly
nano .env
```

Key settings to set:

```env
UVICORN_HOST = "0.0.0.0"
UVICORN_PORT = 8000

# Point Xray at the config file in the data volume
XRAY_JSON = "/var/lib/marzban/xray_config.json"

SQLALCHEMY_DATABASE_URL = "sqlite:////var/lib/marzban/db.sqlite3"

HWID_ENABLED = true
HWID_FALLBACK_LIMIT = 1
```

---

## 3. Write xray_config.json

```bash
sudo mkdir -p /var/lib/marzban
sudo cp xray_config.json /var/lib/marzban/xray_config.json
```

The bundled `xray_config.json` already contains:
- `VLESS-XHTTP-NOTLS` inbound on port **2027** with `noGRPCHeader: true` and `mode: packet-up`
- `SHADOWSOCKS` inbound on port **888**

To customize (e.g. change passwords, ports), edit `/var/lib/marzban/xray_config.json` directly.
Marzban will auto-inject user accounts into it at runtime — **do not add clients manually**.

---

## 4. Build and start Docker container

```bash
cd /home/ubuntu/marzban-fork
docker compose build
docker compose up -d
docker compose logs -f   # watch startup, Ctrl+C to exit
```

Expected in logs:
```
WARNING:  Xray core X.Y.Z started
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Ports exposed by the container:
| Port | Purpose |
|------|---------|
| 8000 | Marzban panel (HTTP or HTTPS depending on .env SSL settings) |
| 2027 | Xray xhttp inbound (plain HTTP — SSL handled by Bunny CDN) |

---

## 5. Install and configure nginx

```bash
sudo apt-get install -y nginx
```

```bash
sudo nano /etc/nginx/sites-available/xhttp
```

Paste:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:2027;
        proxy_http_version 1.1;

        # Critical: without these, nginx buffers the streaming xhttp response
        # and Bunny CDN times out (~2s) before receiving the HTTP 200.
        proxy_buffering off;
        proxy_request_buffering off;

        proxy_read_timeout    300s;
        proxy_send_timeout    300s;
        proxy_connect_timeout  10s;

        chunked_transfer_encoding on;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/xhttp /etc/nginx/sites-enabled/xhttp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl enable nginx && sudo systemctl restart nginx
```

Verify:
```bash
# Should return HTTP 400 (Xray rejecting invalid path — correct, not 502/504)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/
```

---

## 6. Configure Bunny CDN pull zone

In your Bunny CDN pull zone settings:

| Setting | Value |
|---------|-------|
| **Origin URL** | `http://YOUR_SERVER_IP` (port 80 via nginx) |
| **Origin Response Timeout** | `60` seconds or higher (default ~2s causes all 504s) |
| **Disable Smart Cache** | Enable, or set `Cache-Control: no-store` on origin |
| **Forward Host Header** | Enabled |

> The xhttp paths (`/{uuid}` and `/{uuid}/0`) must not be cached.
> Add a cache rule to exclude paths matching `/*` or set TTL to 0.

---

## 7. Create admin account

```bash
docker exec -it marzban-fork-marzban-1 marzban-cli admin create
```

Then open the panel at `http://YOUR_SERVER_IP:8000/dashboard/`.

---

## 8. Add VLESS-XHTTP-NOTLS inbound in panel

1. Go to **Settings → Inbounds** in the Marzban panel
2. Click **Add Inbound** and select `VLESS-XHTTP-NOTLS` (tag from `xray_config.json`)
3. Set the **host** to your Bunny CDN domain (e.g. `maestro969.b-cdn.net`)
4. Set **path** to `/`
5. Save and create a user — subscription links will use the Bunny CDN domain

---

## Updating

```bash
cd /home/ubuntu/marzban-fork
git pull origin main
docker compose build --no-cache
docker compose down && docker compose up -d
```

---

## Troubleshooting

### Still getting 504 from Bunny CDN
1. Check nginx is running: `systemctl status nginx`
2. Check `proxy_buffering off` is in the nginx config: `nginx -T | grep buffering`
3. Check Xray is listening: `ss -tlnp | grep 2027`
4. Check **Bunny CDN origin timeout** — must be ≥ 60s (most common cause)
5. Check container logs: `docker compose logs --tail 50`

### 502 Bad Gateway from nginx
Xray is not listening on port 2027. Check:
```bash
docker compose ps                          # container must be Up
docker compose logs --tail 30              # look for Xray startup errors
ss -tlnp | grep 2027                       # must show docker-proxy
```

### Panel not accessible
Port 8000 must be open in your server firewall:
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 80/tcp
```
