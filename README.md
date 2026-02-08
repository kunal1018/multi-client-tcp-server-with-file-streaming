# Multi-Client TCP Server with File Streaming

A Python-based multi-threaded TCP client–server application that supports
concurrent client connections, command-based interaction, and file streaming
with integrity verification.

## Overview
This project implements a TCP server that can handle multiple clients
simultaneously using threading. Clients interact with the server through a
command-line interface (CLI), send messages, request server status, and
download files from the server’s repository.

The server enforces a maximum number of concurrent clients and maintains
in-memory session metadata, including connection and disconnection timestamps.

## Key Features
- Multi-client support using threading
- Enforced concurrency limit
- Automatic client naming (Client01, Client02, …)
- Command-line interface (CLI)
- File listing and file streaming from server repository
- SHA-256 integrity verification for downloaded files
- Graceful client disconnect handling

## Commands Supported
- `help` – List available commands
- `status` – View connected and disconnected clients
- `list` – List files available on the server
- `get <filename>` – Download a file from the server
- `ping` – Check server responsiveness
- `who` – View currently connected clients
- `uptime` – View server uptime
- `about` – Project information
- `exit` – Disconnect from the server

## Tech Stack
- Python
- TCP sockets
- Threading
- SHA-256 hashing

## How to Run
1. Start the server:
   ```bash
   python3 Server.py
