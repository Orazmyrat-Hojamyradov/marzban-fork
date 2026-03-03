import io
import ipaddress
import json
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from telebot import types

from app.db import GetDB, crud
from app.telegram import bot
from config import TELEGRAM_ADMIN_ID

BUNNY_CDN_API = "bunnycdn.com"
BUNNY_CDN_PATH = "/api/system/edgeserverlist"
TCP_TEST_PORT = 443
TCP_TIMEOUT = 3
SERVER_VERIFY_TIMEOUT = 5

PING_SCRIPT_TEMPLATE = '''\
import socket
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

IPS = {ips}

PORT = 443
TIMEOUT = 5
RESULTS = []


def test_ip(ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        start = time.time()
        s.connect((ip, PORT))
        latency = round((time.time() - start) * 1000, 2)
        s.close()
        return (ip, latency)
    except Exception:
        return (ip, None)


print("Testing", len(IPS), "IPs on port", PORT, "...")

with ThreadPoolExecutor(max_workers=20) as pool:
    futures = {{pool.submit(test_ip, ip): ip for ip in IPS}}
    for f in as_completed(futures):
        ip, latency = f.result()
        if latency is not None:
            RESULTS.append((ip, latency))
            print(f"  {{ip}} -> {{latency}} ms")
        else:
            print(f"  {{ip}} -> timeout")

RESULTS.sort(key=lambda x: x[1])

with open("ips.txt", "w") as f:
    for ip, latency in RESULTS:
        print(f"{{ip}} {{latency}}", file=f)

print()
if RESULTS:
    print(f"Best: {{RESULTS[0][0]}} ({{RESULTS[0][1]}} ms)")
    print(f"Written {{len(RESULTS)}} reachable IPs to ips.txt")
else:
    print("No reachable IPs found.")
'''


def fetch_bunny_ips():
    """Fetch Bunny CDN edge server IPs via HTTPS."""
    ctx = ssl.create_default_context()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ss = ctx.wrap_socket(s, server_hostname=BUNNY_CDN_API)
    ss.settimeout(10)
    ss.connect((BUNNY_CDN_API, 443))
    request = (
        f"GET {BUNNY_CDN_PATH} HTTP/1.1\r\n"
        f"Host: {BUNNY_CDN_API}\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n\r\n"
    )
    ss.sendall(request.encode())

    response = b""
    while True:
        chunk = ss.recv(4096)
        if not chunk:
            break
        response += chunk
    ss.close()

    body = response.split(b"\r\n\r\n", 1)[1]
    # Handle chunked transfer encoding
    try:
        ips = json.loads(body)
    except json.JSONDecodeError:
        # Decode chunked body
        decoded = b""
        remaining = body
        while remaining:
            line_end = remaining.find(b"\r\n")
            if line_end == -1:
                break
            chunk_size = int(remaining[:line_end], 16)
            if chunk_size == 0:
                break
            decoded += remaining[line_end + 2:line_end + 2 + chunk_size]
            remaining = remaining[line_end + 2 + chunk_size + 2:]
        ips = json.loads(decoded)

    # Filter to valid IPv4 only
    result = []
    for ip in ips:
        ip = ip.strip()
        try:
            addr = ipaddress.ip_address(ip)
            if addr.version == 4:
                result.append(ip)
        except ValueError:
            continue
    return result


def server_tcp_latency(ip):
    """Test TCP latency from server to an IP on port 443. Returns ms or None."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SERVER_VERIFY_TIMEOUT)
        start = time.time()
        s.connect((ip, TCP_TEST_PORT))
        latency = round((time.time() - start) * 1000, 2)
        s.close()
        return latency
    except Exception:
        return None


def verify_ips_from_server(ips):
    """Verify a list of IPs are reachable from the server. Returns set of reachable IPs."""
    reachable = set()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(server_tcp_latency, ip): ip for ip in ips}
        for f in as_completed(futures):
            ip = futures[f]
            if f.result() is not None:
                reachable.add(ip)
    return reachable


@bot.message_handler(commands=['smarthost'], is_admin=True)
def smarthost_command(message: types.Message):
    """Generate and send a ping test script with Bunny CDN IPs."""
    bot.send_message(message.chat.id, "Fetching Bunny CDN edge IPs...")

    try:
        ips = fetch_bunny_ips()
    except Exception as e:
        bot.send_message(message.chat.id, f"Failed to fetch Bunny CDN IPs: {e}")
        return

    if not ips:
        bot.send_message(message.chat.id, "No IPs found from Bunny CDN API.")
        return

    script_content = PING_SCRIPT_TEMPLATE.format(ips=repr(ips))

    doc = io.BytesIO(script_content.encode('utf-8'))
    doc.name = "ping_test.py"

    bot.send_document(
        message.chat.id,
        doc,
        caption=f"Ping test script with {len(ips)} Bunny CDN IPs.\n"
                "Give this to the user to run with Python (Termux/iSH).\n"
                "They should send back the resulting ips.txt file."
    )


@bot.message_handler(content_types=['document'], is_admin=True)
def handle_document(message: types.Message):
    """Handle ips.txt file uploads from admin."""
    doc = message.document
    if not doc.file_name or not doc.file_name.endswith('.txt'):
        return

    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    content = downloaded.decode('utf-8', errors='ignore')

    # Parse ips.txt: each line is "ip latency_ms"
    user_results = []
    for line in content.strip().splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        ip, latency_str = parts
        try:
            ipaddress.ip_address(ip)
            latency = float(latency_str)
            user_results.append((ip, latency))
        except (ValueError, TypeError):
            continue

    if not user_results:
        bot.send_message(message.chat.id, "Could not parse any valid IP entries from the file.")
        return

    bot.send_message(
        message.chat.id,
        f"Parsed {len(user_results)} IPs from file. Verifying from server..."
    )

    # Server-side verification
    candidate_ips = [ip for ip, _ in user_results]
    reachable = verify_ips_from_server(candidate_ips)

    # Pick best IP: lowest user latency among server-verified IPs
    verified_results = [(ip, lat) for ip, lat in user_results if ip in reachable]
    verified_results.sort(key=lambda x: x[1])

    if not verified_results:
        bot.send_message(
            message.chat.id,
            "None of the user's IPs are reachable from the server."
        )
        return

    best_ip, best_latency = verified_results[0]

    # Show summary and ask for username
    summary = (
        f"Server-verified: {len(verified_results)}/{len(user_results)} IPs\n"
        f"Best IP: {best_ip} ({best_latency} ms user latency)\n\n"
        f"Top 5:\n"
    )
    for ip, lat in verified_results[:5]:
        summary += f"  {ip} - {lat} ms\n"

    summary += "\nType the username to assign this IP to:"

    msg = bot.send_message(message.chat.id, summary)
    bot.register_next_step_handler(msg, lambda m: assign_smart_host(m, best_ip, best_latency))


def assign_smart_host(message: types.Message, best_ip: str, best_latency: float):
    """Assign the best smart host IP to a user."""
    if message.chat.id not in TELEGRAM_ADMIN_ID:
        return

    username = message.text.strip()
    if not username:
        bot.send_message(message.chat.id, "No username provided. Operation cancelled.")
        return

    with GetDB() as db:
        dbuser = crud.get_user(db, username)
        if not dbuser:
            bot.send_message(message.chat.id, f"User '{username}' not found.")
            return

        old_host = dbuser.smart_host_address or "(none)"
        crud.update_user_smart_host(db, dbuser, best_ip)

    bot.send_message(
        message.chat.id,
        f"Updated smart host for '{username}':\n"
        f"  Old: {old_host}\n"
        f"  New: {best_ip} ({best_latency} ms user latency)"
    )
