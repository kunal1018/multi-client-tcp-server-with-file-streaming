#!/usr/bin/env python3
# ============================================================
# CP372 – Client (plain, no ANSI) – Fall 2025
# Team:
#   Kunal Gandhi (169051546) — gand1546@mylaurier.ca
#   Muzzi Khan  (169073561)  — khan3561@mylaurier.ca
# Demo Slot: Oct 24, 2025 @ 10:30 AM
# ============================================================

import socket
import os
import hashlib

HOST = '127.0.0.1'   # must match Server.py
PORT = 50000         # must match Server.py
ENCODING = 'utf-8'
BUFF_SIZE = 4096
DOWNLOADS = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DOWNLOADS, exist_ok=True)

def send_line(sock, text: str):
    sock.sendall((text + '\n').encode(ENCODING))

def recv_line(sock) -> str:
    data = bytearray()
    while True:
        ch = sock.recv(1)
        if not ch:
            break
        if ch == b'\n':
            break
        data.extend(ch)
    return data.decode(ENCODING, errors='replace').strip()

def receive_file(sock, header: str):
    # header: "FILE <filename> <size> <sha256>"
    parts = header.split(maxsplit=3)
    if len(parts) != 4:
        print('[CLIENT] Bad FILE header from server'); return
    _, filename, size_str, digest = parts
    try:
        size = int(size_str)
    except ValueError:
        print('[CLIENT] Invalid file size in header'); return

    out_path = os.path.join(DOWNLOADS, filename)
    remaining = size
    h = hashlib.sha256()
    with open(out_path, 'wb') as f:
        while remaining > 0:
            chunk = sock.recv(min(BUFF_SIZE, remaining))
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            remaining -= len(chunk)
    trailer = recv_line(sock)  # expect 'FILE DONE'
    ok = (h.hexdigest() == digest)
    print(f"[CLIENT] Saved file to: {out_path}")
    print(f"[CLIENT] SHA256 verify: {'PASS' if ok else 'FAIL'}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # connect to server
        sock.connect((HOST, PORT))

        # greeting from server
        line = recv_line(sock)
        if line == 'SERVER FULL':
            print('[CLIENT] Server is at capacity. Try again later.')
            return
        if not line.startswith('NAME '):
            print('[CLIENT] Unexpected greeting:', line)
            return

        assigned = line.split(' ', 1)[1]

        # handshake: tell server our name
        send_line(sock, f'NAME {assigned}')
        print('[CLIENT] Assigned name:', assigned)

        # welcome line
        print('[SERVER]', recv_line(sock))
        print('Commands: help | list | status | who | ping | uptime | get <file> | <filename> | about | exit')

        while True:
            try:
                msg = input(f'{assigned} > ').strip()
            except (EOFError, KeyboardInterrupt):
                msg = 'exit'

            if not msg:
                continue

            send_line(sock, msg)

            if msg.lower() == 'exit':
                print('[SERVER]', recv_line(sock))
                break

            # First response decides how to read the rest
            resp = recv_line(sock)

            if resp == 'STATUS BEGIN':
                print('[SERVER] --- STATUS ---')
                while True:
                    line = recv_line(sock)
                    if line == 'STATUS END' or line == '':
                        break
                    print(line)
                print('[SERVER] ---------------')

            elif resp == 'FILES BEGIN':
                print('[SERVER] --- FILES ---')
                while True:
                    line = recv_line(sock)
                    if line == 'FILES END' or line == '':
                        break
                    print(line)
                print('[SERVER] --------------')

            elif resp.startswith('FILE '):
                receive_file(sock, resp)

            else:
                # one-line responses: ACK, HELP text, WHO list, PONG, UPTIME, ABOUT, FILEERR, WARN/ERR...
                print('[SERVER]', resp)

if __name__ == '__main__':
    try:
        main()
    except ConnectionRefusedError:
        print('[CLIENT] Could not connect to 127.0.0.1:50000 — is the server running?')
