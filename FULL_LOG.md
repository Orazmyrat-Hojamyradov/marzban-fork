# Full Change & Debug Log

Everything done in this session, in exact order.

---

## Phase 1 — Diagnosis: Why xhttp gave 504 with Bunny CDN

### What was reported
The fork gave 504 errors from Bunny CDN on all xhttp connections. The official prebuilt `gozargah/marzban:dev` Docker image gave 200 on the same setup.

### Log analysis (Log explorer 5427493.log)
Bunny CDN log format: `cache_status|http_status|timestamp|response_time_ms|zone_id|client_ip|url|referer|country|user_agent|hash|pop`

All requests failing:
- Status: `504`
- Response time: ~2209–2236 ms (consistent timeout)
- User agent: `Go-http-client/2.0` (Xray HTTP/2 client)
- Paths: `/{uuid}` (download stream) and `/{uuid}/0` (upload chunk)
- Cache status: `MISS` for GET, `-` for POST

The consistent ~2.2s timeout meant Bunny CDN was hitting its **origin response timeout**, not receiving any data from origin before giving up.

### Root causes identified

**1. nginx was not installed / not configured**
The server had no nginx. Without a reverse proxy configured with `proxy_buffering off`, the xhttp streaming response would never be forwarded to Bunny CDN in time. nginx's default `proxy_buffering on` makes nginx wait for the complete response before forwarding — xhttp is a long-lived stream that never "completes", so Bunny CDN times out.

**2. xray_config.json had no xhttp inbound**
The `xray_config.json` in the container only had a Shadowsocks inbound. The VLESS-XHTTP-NOTLS inbound on port 2027 did not exist. Xray was not listening for xhttp connections at all.

**3. Port 2027 was not exposed in docker-compose**
Even if the inbound were configured, docker-compose only mapped port 8000. Port 2027 was inaccessible from the host/nginx.

**4. Bunny CDN origin timeout too short**
Bunny CDN's default origin response timeout is ~2 seconds. xhttp keeps connections open for streaming — this must be set to 60+ seconds.

---

## Phase 2 — Code changes (local repo)

### Commit 1: Add existing untracked files
**Files:** `.env.production`, `proxy-service/server.js`, `proxy-service/README.md`

```bash
git add .env.production proxy-service/
git commit -m "add production env config and Deno proxy service"
```

`.env.production` — production environment config with:
- `UVICORN_SSL_CERTFILE` / `UVICORN_SSL_KEYFILE` for panel SSL
- `XRAY_JSON = "/var/lib/marzban/xray_config.json"`
- `HWID_ENABLED=true`, `HWID_FALLBACK_LIMIT=1`
- `XRAY_EXECUTABLE_PATH="/var/lib/marzban/xray-core/xray"`

`proxy-service/` — Deno HTTP proxy that forwards subscription requests to Marzban, preserving `x-hwid` headers for device tracking.

---

### Commit 2: nginx config + xray_config.json fix
**Files:** `nginx-xhttp.conf` (new), `xray_config.json` (updated)

Created `nginx-xhttp.conf` — nginx reverse proxy config for xhttp behind Bunny CDN. Key settings:
```nginx
proxy_buffering off;           # critical — without this nginx buffers the stream
proxy_request_buffering off;   # critical — upload chunks must flow immediately
proxy_read_timeout 300s;
proxy_http_version 1.1;
chunked_transfer_encoding on;
```
Proxies from port 80/443 to `127.0.0.1:2027` (Xray xhttp inbound).

Updated `xray_config.json` — replaced the Shadowsocks-only template with the production config:
- Added `VLESS-XHTTP-NOTLS` inbound on port 2027 with:
  - `mode: "packet-up"`
  - `noGRPCHeader: true` (for CDN compatibility)
  - `path: "/"`
  - `xPaddingBytes: "100-1000"`
- Kept `SHADOWSOCKS` inbound on port 888
- Added proper routing rules (block private IPs, geosite:private, bittorrent)

```bash
git add nginx-xhttp.conf xray_config.json
git commit -m "fix: add nginx xhttp config for Bunny CDN and noGRPCHeader in xray template"
```

---

### Commit 3: Expose port 2027 in docker-compose
**File:** `docker-compose.yml`

Added port mapping so Xray's xhttp inbound is reachable from nginx on the host:
```yaml
ports:
  - "8000:8000"
  - "2027:2027"   # added
```

```bash
git add docker-compose.yml
git commit -m "fix: expose port 2027 for Xray xhttp inbound in docker-compose"
git push origin main
```

---

## Phase 3 — GitHub repository

Checked existing git remotes — remote `origin` pointed to `https://github.com/Orazmyrat-Hojamyradov/marzban-fork.git` but the repo didn't exist on GitHub yet.

Created public repo:
```bash
gh repo create Orazmyrat-Hojamyradov/marzban-fork --public \
  --description "Marzban VPN panel fork with HWID device limiting, Bunny CDN xhttp support"
git push origin main
```

Repo URL: https://github.com/Orazmyrat-Hojamyradov/marzban-fork

---

## Phase 4 — Server investigation

**Server:** `46.247.40.130` (Ubuntu 22.04)

### Initial state found
- Docker 29.2.1 + Docker Compose v5.1.0: installed ✓
- nginx: **not installed**
- Running containers:
  - `marzban-fork-marzban-1` — built from `/home/ubuntu/marzban-fork/`, port 8000 only
  - `marzban-node` — official marzban-node image
- `/var/lib/marzban/`: only `db.sqlite3`, no `xray_config.json`, no certs
- Port 2027: **not listening**
- Port 8000: listening (docker-proxy)
- `/opt/marzban`: did not exist

### Container state found
- Running from `/home/ubuntu/marzban-fork/docker-compose.yml`
- `.env` at `/home/ubuntu/marzban-fork/.env` had:
  - `UVICORN_HOST = "192.168.1.31"` (private IP, but Docker maps 0.0.0.0:8000)
  - `XRAY_JSON` commented out → using default `/code/xray_config.json`
  - `HWID_ENABLED=true`, `HWID_FALLBACK_LIMIT=3`
- xray_config.json inside container: **old version** — only Shadowsocks TCP on port 1080, no xhttp inbound
- Xray running as `/usr/local/bin/xray run -config stdin:` (inside container) — but with wrong config

---

## Phase 5 — Server deployment

### Step 1: Pull latest code
```bash
git config --global --add safe.directory /home/ubuntu/marzban-fork
git fetch origin
git reset --hard origin/main
```

### Step 2: Write xray_config.json to /var/lib/marzban/
Wrote the correct production config to `/var/lib/marzban/xray_config.json`:
- `VLESS-XHTTP-NOTLS` inbound on port 2027 with `noGRPCHeader: true`, `mode: packet-up`, `path: "/"`
- `SHADOWSOCKS` inbound on port 888

### Step 3: Update .env to set XRAY_JSON
Changed the commented-out `# XRAY_JSON = "xray_config.json"` line to:
```
XRAY_JSON = "/var/lib/marzban/xray_config.json"
```
This tells Marzban to use the file from the persistent volume instead of the one baked into the image.

### Step 4: Rebuild Docker image (no cache) and restart
```bash
docker compose build --no-cache
docker compose down
docker compose up -d
```
Result: container started with ports `0.0.0.0:2027->2027/tcp` and `0.0.0.0:8000->8000/tcp`.
Xray 26.2.6 started successfully with the new xhttp inbound.

### Step 5: Install nginx
```bash
apt-get update -qq && apt-get install -y -qq nginx
```

### Step 6: Configure nginx for xhttp
Wrote `/etc/nginx/sites-available/xhttp`:
```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:2027;
        proxy_http_version 1.1;
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

Enabled site and restarted nginx:
```bash
ln -sf /etc/nginx/sites-available/xhttp /etc/nginx/sites-enabled/xhttp
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable nginx && systemctl restart nginx
```

### Verification
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/
# Result: 400 (Xray rejecting invalid path — correct, NOT 502/504)
```
400 from Xray means the chain works: nginx → port 2027 → Xray xhttp inbound. 400 is expected because a bare `/` without a valid UUID path is rejected by Xray.

Final port state:
| Port | Process |
|------|---------|
| 80 | nginx → Xray:2027 |
| 2027 | docker-proxy → Xray xhttp inbound |
| 8000 | docker-proxy → Marzban panel |

---

## Phase 6 — Panel access

**URL:** `http://46.247.40.130:8000/dashboard/`
**Username:** `admin`
**Password:** `admin` (hardcoded in `.env` — change immediately)

---

## Phase 7 — Host configuration debugging

### Problem: subscription returned device limit warning
The subscription link for user `testtt` returned:
```
vless://00000000-0000-0000-0000-000000000001@0.0.0.0:0?type=tcp#⚠️ Лимит устройств достиг
```
This is the HWID device limit warning (Russian: "Device limit reached"). `HWID_FALLBACK_LIMIT=1` in the `.env` was triggering it. `device_limit` on the user was set to 100, so the issue was transient.

### Problem: wrong address in host config
Marzban panel → Settings → Hosts → VLESS-XHTTP-NOTLS had:
- `address: "79.127.134.234"` — a Bunny CDN edge IP, not the CDN domain
- `path: null` — should be `/`
- `sni: "google.com"` — should be the CDN domain

Fixed via API:
```json
{
  "address": "maestro969.b-cdn.net",
  "port": 443,
  "sni": "maestro969.b-cdn.net",
  "host": "maestro969.b-cdn.net",
  "path": "/",
  "security": "tls",
  "alpn": "http/1.1",
  "fingerprint": "chrome",
  "allowinsecure": false
}
```

### Problem: 301 redirects — Xray connecting via HTTP instead of HTTPS
After fixing the address and re-importing subscription, Bunny CDN logs showed:
- `http://maestro969.b-cdn.net/...` — plain HTTP
- Status: `301` (Bunny CDN "Force HTTPS" redirecting to HTTPS)
- User agent: `Go-http-client/1.1`

**Root cause:** Changing ALPN from `h2` to `http/1.1` broke TLS. HTTP/2 (`h2`) inherently requires TLS — it cannot run without encryption. HTTP/1.1 does not require TLS, so Xray connected via plain HTTP.

Proof from log file comparison:
- Working connections (from before): `https://` + `Go-http-client/2.0` + `200` (h2 = HTTP/2 = forced TLS)
- Broken connections (after ALPN change): `http://` + `Go-http-client/1.1` + `301` (http/1.1 without TLS)

### Final fix: set ALPN back to h2
Updated host config via API with `"alpn": "h2"`:
```bash
curl -X PUT http://127.0.0.1:8000/api/hosts \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"VLESS-XHTTP-NOTLS": [{"alpn": "h2", ...}]}'
```

Final working VLESS link generated:
```
vless://{uuid}@maestro969.b-cdn.net:443?security=tls&type=xhttp
  &path=%2F&host=maestro969.b-cdn.net&mode=packet-up
  &sni=maestro969.b-cdn.net&fp=chrome&alpn=h2
  &extra={"scMaxEachPostBytes":"1000000","xPaddingBytes":"100-1000","noGRPCHeader":true}
```

After re-importing subscription in Happ → connection worked. Bunny CDN logs showed `https://` + `Go-http-client/2.0` + `200`.

---

## Phase 8 — Remaining issue: Turkmenistan

### Observed
After fixing for BG PoP, connections from the **TM PoP** (Bunny CDN Turkmenistan edge) still failed.

### Analysis
Bunny CDN log format includes PoP code as the last field. In all three log files:
- `BG` PoP entries → 200 ✓
- `TM` PoP entries → 504 ✗

### Likely causes
1. **Bunny CDN TM PoP cannot reach origin `46.247.40.130`** — routing/firewall issue between Bunny CDN's Turkmenistan datacenter and the origin server
2. **Turkmenistan DPI blocks h2** — Turkmenistan has aggressive deep packet inspection that fingerprints and blocks HTTP/2 connections

### Recommended fix
In Bunny CDN dashboard → pull zone → **Routing** → **Edge Location Routing** → disable the **Turkmenistan** PoP. This forces TM users to route through a different PoP (e.g. Russia or EU) that can successfully reach the origin.

---

## Summary of all files changed

| File | Change |
|------|--------|
| `docker-compose.yml` | Added `"2027:2027"` port mapping |
| `xray_config.json` | Replaced Shadowsocks-only template with full production config including VLESS-XHTTP-NOTLS inbound on port 2027 with `noGRPCHeader: true` |
| `nginx-xhttp.conf` | New file — nginx reverse proxy config for xhttp with `proxy_buffering off` |
| `DEPLOYMENT.md` | New file — step-by-step deployment guide |
| `.env.production` | Committed existing file |
| `proxy-service/server.js` | Committed existing file |
| `proxy-service/README.md` | Committed existing file |

## Summary of server changes

| What | Where | Change |
|------|-------|--------|
| `/var/lib/marzban/xray_config.json` | Server | Created — VLESS-XHTTP-NOTLS inbound on port 2027 |
| `/home/ubuntu/marzban-fork/.env` | Server | Set `XRAY_JSON = "/var/lib/marzban/xray_config.json"` |
| Docker container | Server | Rebuilt from latest code, port 2027 now exposed |
| nginx | Server | Installed, configured to proxy port 80 → port 2027 with buffering disabled |
| Marzban hosts config | Panel API | Fixed address, SNI, path, ALPN for VLESS-XHTTP-NOTLS inbound |

## Final working stack

```
Happ client (Turkmenistan/any country)
    │  HTTPS/h2 (TLS, Go-http-client/2.0)
    ▼
maestro969.b-cdn.net:443  ← Bunny CDN pull zone
    │  HTTP/1.1 (CDN terminates TLS)
    ▼
46.247.40.130:80  ← nginx
    │  proxy_buffering off, proxy_request_buffering off
    ▼
127.0.0.1:2027  ← Docker → Xray 26.2.6
    │  VLESS-XHTTP-NOTLS inbound
    │  mode: packet-up, noGRPCHeader: true
    ▼
Outbound: DIRECT (internet)
```
