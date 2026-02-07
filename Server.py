#!/usr/bin/env python3
# ============================================================
# CP372 – Programming Assignment (Socket Programming) – Fall 2025
# Instructor: Dr. Lilatul Ferdouse
#
# Team:
#   Kunal Gandhi (169051546) — gand1546@mylaurier.ca
#   Muzzi Khan  (169073561)  — khan3561@mylaurier.ca
# Demo Slot: Oct 24, 2025 @ 10:30 AM
#
# Notes:
# - Multi-threaded TCP server with a 3-client concurrency cap
# - Commands: help, status, list, get <file>, <filename>, ping, who, uptime, about, exit
# - File streaming uses a header with size and SHA-256 digest; client verifies
# - In-memory cache: accepted/finished/addr; pretty status table
# - All messages plain text (no ANSI), clean logs, graceful shutdown
# ============================================================

import socket
import threading
import os
import logging
import hashlib
import signal
import sys
from datetime import datetime
import time

# ===== Team / Version =====
TEAM = "Kunal Gandhi & Muzzi Khan"
VERSION = "1.2"

# ===== Config (defaults; keep 3 for rubric) =====
HOST = '127.0.0.1'           # Change to '0.0.0.0' for LAN demo
PORT = 50000
REPO_DIR = os.path.join(os.path.dirname(__file__), 'server_repo')
MAX_CLIENTS = 3

# ===== Globals =====
os.makedirs(REPO_DIR, exist_ok=True)
state_lock = threading.Lock()
client_counter = 0
# cache: {client_name: {"accepted": str, "finished": str|None, "addr": (ip,port)}}
cache = {}
active_clients = set()
capacity_sem = threading.Semaphore(MAX_CLIENTS)

ENCODING = 'utf-8'
BUFF_SIZE = 4096
START_TS = time.time()

def now_iso():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def send_line(conn, text: str):
    """Send a single line terminated by \\n (control channel)."""
    conn.sendall((text + '\n').encode(ENCODING))

def recv_line(conn) -> str:
    """Read until \\n or EOF; return decoded string without newline."""
    data = bytearray()
    while True:
        chunk = conn.recv(1)
        if not chunk or chunk == b'\n':
            break
        data.extend(chunk)
    return data.decode(ENCODING, errors='replace').strip()

def list_files():
    try:
        return [f for f in os.listdir(REPO_DIR) if os.path.isfile(os.path.join(REPO_DIR, f))]
    except Exception as e:
        return [f"<error: {e}>"]

def safe_name(name: str) -> bool:
    """Basic path-traversal protection."""
    bad = ('..' in name) or name.startswith('/') or ('/' in name) or ('\\' in name)
    return not bad

def send_file(conn: socket.socket, filename: str):
    """Stream a file with size + SHA256 header, then 'FILE DONE' trailer."""
    if not safe_name(filename):
        send_line(conn, 'FILEERR invalid-name')
        return
    path = os.path.join(REPO_DIR, filename)
    if not os.path.isfile(path):
        send_line(conn, f'FILEERR not-found {filename}')
        return
    try:
        size = os.path.getsize(path)
        # compute SHA256 first (single pass)
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(BUFF_SIZE), b''):
                h.update(chunk)
        digest = h.hexdigest()

        # header includes size and hash
        send_line(conn, f'FILE {filename} {size} {digest}')

        # stream bytes
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(BUFF_SIZE), b''):
                conn.sendall(chunk)

        send_line(conn, 'FILE DONE')
        logging.info(f"Sent file '{filename}' size={size} sha256={digest[:12]}…")
    except Exception as e:
        send_line(conn, f'FILEERR {e}')

def handle_client(conn: socket.socket, addr):
    """Per-connection thread: handshake, command loop, cleanup."""
    global client_counter
    client_name = None
    try:
        # Enforce capacity BEFORE assigning name (but we already acquired semaphore in accept loop)
        with state_lock:
            client_counter += 1
            client_name = f"Client{client_counter:02d}"
            active_clients.add(client_name)
            cache[client_name] = {"accepted": now_iso(), "finished": None, "addr": addr}

        logging.info(f"Connected: {client_name} from {addr}")
        send_line(conn, f"NAME {client_name}")

        # Expect client to communicate back NAME
        line = recv_line(conn)
        if not line or not line.startswith('NAME '):
            send_line(conn, 'ERR expected NAME <clientName>')
        else:
            claimed = line.split(' ', 1)[1].strip()
            if claimed != client_name:
                send_line(conn, f'WARN name-mismatch, using {client_name}')

        # Plain welcome
        send_line(conn, f"WELCOME {client_name} | SERVER v{VERSION}")

        # Command loop
        while True:
            line = recv_line(conn)
            if not line:
                break
            cmd = line.strip()

            if cmd.lower() == 'exit':
                send_line(conn, "BYE")
                break

            elif cmd.lower() == 'status':
                with state_lock:
                    rows = [(c, info['accepted'], str(info['finished']), str(info['addr']))
                            for c, info in cache.items()]
                send_line(conn, 'STATUS BEGIN')
                send_line(conn, f"{'CLIENT':<10} {'ACCEPTED':<19} {'FINISHED':<19} {'ADDR'}")
                for c, a, f, ainfo in rows:
                    send_line(conn, f"{c:<10} {a:<19} {f:<19} {ainfo}")
                send_line(conn, 'STATUS END')

            elif cmd.lower() == 'list':
                files = list_files()
                send_line(conn, 'FILES BEGIN')
                for f in files:
                    send_line(conn, f)
                send_line(conn, 'FILES END')

            elif cmd.lower().startswith('get '):
                filename = cmd[4:].strip()
                send_file(conn, filename)

            elif cmd.lower() == 'help':
                send_line(conn, 'CMDS: help | status | list | get <file> | <filename> | ping | who | uptime | about | exit')

            elif cmd.lower() == 'who':
                with state_lock:
                    names = ", ".join(sorted(active_clients)) if active_clients else "<none>"
                send_line(conn, f'WHO {names}')

            elif cmd.lower() == 'ping':
                send_line(conn, "PONG")

            elif cmd.lower() == 'uptime':
                send_line(conn, f'UPTIME {int(time.time()-START_TS)}s')

            elif cmd.lower() == 'about':
                send_line(conn, f'ABOUT Team: {TEAM} | Demo: Oct 24, 10:30 AM | Version: {VERSION}')

            else:
                # treat as filename if exists, else echo with ACK
                path = os.path.join(REPO_DIR, cmd)
                if safe_name(cmd) and os.path.isfile(path):
                    send_file(conn, cmd)
                else:
                    send_line(conn, f"{cmd} ACK")

    except Exception as e:
        try:
            send_line(conn, f'ERR {e}')
        except Exception:
            pass
        logging.exception(f"Handler error for {client_name}")
    finally:
        conn.close()
        with state_lock:
            if client_name in active_clients:
                active_clients.remove(client_name)
            if client_name in cache:
                cache[client_name]['finished'] = now_iso()
        capacity_sem.release()
        logging.info(f"Finished: {client_name}")

def serve_forever():
    logging.info(f"Starting server on {HOST}:{PORT}, repo='{REPO_DIR}', max_clients={MAX_CLIENTS}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            # capacity check
            acquired = capacity_sem.acquire(blocking=False)
            if not acquired:
                try:
                    send_line(conn, 'SERVER FULL')
                except Exception:
                    pass
                conn.close()
                continue
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

def _sigint(_sig, _frm):
    logging.info("Shutting down server gracefully…")
    sys.exit(0)

if __name__ == '__main__':
    logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.INFO)
    signal.signal(signal.SIGINT, _sigint)
    # Simple, professional one-liner banner (stdout only; not sent to clients)
    print(f"CP372 Socket Server | Team: {TEAM} | v{VERSION}")
    serve_forever()
