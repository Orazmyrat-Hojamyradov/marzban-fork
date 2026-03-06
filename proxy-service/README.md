# Proxy Service

Deno-based HTTP proxy that forwards subscription requests to Marzban, preserving client headers (including `x-hwid` for device tracking).

## Why

Apps like Happ send device identification headers (`x-hwid`, `x-device-model`, etc.) with subscription requests. This proxy sits between the app and Marzban, forwarding all headers transparently so HWID-based device limiting works correctly.

## Requirements

- [Deno](https://deno.land) installed on the proxy server

```bash
curl -fsSL https://deno.land/install.sh | sh
```

## Deploy

```bash
# Copy server.js to the server
scp server.js root@YOUR_SERVER:/opt/proxy-service/server.js

# Or create the directory and file manually
mkdir -p /opt/proxy-service
# paste server.js contents
```

## Commands

### Start

```bash
# Foreground (see logs in terminal)
deno run --allow-net /opt/proxy-service/server.js

# Background with logging
nohup deno run --allow-net /opt/proxy-service/server.js > /tmp/proxy.log 2>&1 &
```

### Stop

```bash
kill $(pgrep -f "deno.*server.js")
```

### Restart

```bash
kill $(pgrep -f "deno.*server.js") 2>/dev/null
sleep 1
nohup deno run --allow-net /opt/proxy-service/server.js > /tmp/proxy.log 2>&1 &
```

### View logs

```bash
# Live logs
tail -f /tmp/proxy.log

# Last 50 lines
tail -50 /tmp/proxy.log

# Full log
cat /tmp/proxy.log
```

### Check if running

```bash
ps aux | grep deno | grep -v grep
```

## Usage

The proxy listens on port `3000`.

```
# Raw mode — returns upstream response as-is
GET /?url=https://your-marzban.com/sub/TOKEN

# JSON mode — returns headers + status + body as JSON
GET /?url=https://your-marzban.com/sub/TOKEN&format=json
```

### Test with curl

```bash
# Basic test
curl "http://localhost:3000/?url=https://example.com"

# Test with x-hwid header
curl -H "x-hwid: test123" "http://localhost:3000/?url=https://your-marzban.com/sub/TOKEN"

# JSON mode (see all upstream headers)
curl "http://localhost:3000/?url=https://your-marzban.com/sub/TOKEN&format=json"
```

## Header handling

### Request (client -> upstream)

All client headers are forwarded **except** hop-by-hop and encoding headers:
`host`, `connection`, `te`, `trailers`, `transfer-encoding`, `upgrade`, `accept-encoding`, `content-length`, `content-type`

Headers like `x-hwid`, `x-device-model`, `user-agent`, etc. are forwarded as-is.

### Response (upstream -> client)

All upstream headers are forwarded **except** encoding headers that Deno auto-handles:
`content-encoding`, `content-length`, `transfer-encoding`

CORS headers are added automatically:
`access-control-allow-origin: *`, `access-control-expose-headers: *`

## Systemd service (optional)

Create `/etc/systemd/system/proxy-service.service`:

```ini
[Unit]
Description=Deno Proxy Service
After=network.target

[Service]
ExecStart=/root/.deno/bin/deno run --allow-net /opt/proxy-service/server.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable proxy-service
systemctl start proxy-service

# Logs via journalctl
journalctl -u proxy-service -f
```
