#!/usr/bin/env python3
"""Persistent telnet client for the local tbaMUD server.

Runs as a small background daemon holding one open telnet connection,
so a series of `send`/`read` calls from a chat session can drive a single
continuous MUD session without reconnecting (and re-logging-in) each time.

Usage:
    mud_client.py start                 # connect + auto-login, print welcome text
    mud_client.py send "look"           # send a command, print the response
    mud_client.py send "north" --wait 2 # send a command, wait longer for slow replies
    mud_client.py read                  # print any new output without sending anything
    mud_client.py read --wait 3         # wait, then print new output (e.g. during combat)
    mud_client.py status                # is the daemon alive? show last output
    mud_client.py stop                  # quit the game cleanly and kill the daemon

All subcommands operate on a session directory (default /tmp/tbamud-session)
that holds the daemon's pid, a FIFO for sending commands in, and a growing
output.log that callers tail via a saved cursor position.
"""
import argparse
import os
import re
import select
import signal
import socket
import subprocess
import sys
import time

HOST = "localhost"
PORT = 4000
USERNAME = "dummy"
PASSWORD = "helloworld"

DEFAULT_SESSION_DIR = os.environ.get("MUD_SESSION_DIR", "/tmp/tbamud-session")

IAC = 0xFF
IAC_RE = re.compile(rb"\xff[\xfb-\xfe]." + rb"|\xff\xfa.*?\xff\xf0" + rb"|\xff.", re.DOTALL)
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")


def clean(data: bytes) -> bytes:
    data = IAC_RE.sub(b"", data)
    data = ANSI_RE.sub(b"", data)
    return data


def paths(session_dir):
    return {
        "dir": session_dir,
        "pid": os.path.join(session_dir, "session.pid"),
        "fifo": os.path.join(session_dir, "commands.fifo"),
        "log": os.path.join(session_dir, "output.log"),
        "cursor": os.path.join(session_dir, "cursor.txt"),
        "daemon_log": os.path.join(session_dir, "daemon.log"),
    }


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def read_pid(p):
    try:
        with open(p["pid"]) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running(p):
    pid = read_pid(p)
    return pid is not None and pid_alive(pid)


# --------------------------------------------------------------------------
# Daemon: owns the telnet socket, logs in, then relays FIFO commands in and
# MUD output out until the connection dies or it's killed.
# --------------------------------------------------------------------------

def wait_for(sock, log_f, patterns, timeout):
    """Read from sock until one of the byte-string patterns shows up in the
    buffer, echoing everything read to the log as we go. Returns the matched
    pattern, or None if we time out (the caller decides whether that's fatal)."""
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        r, _, _ = select.select([sock], [], [], max(0, remaining))
        if not r:
            break
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("MUD closed connection during login")
        buf += chunk
        cleaned = clean(chunk)
        log_f.write(cleaned)
        log_f.flush()
        for pat in patterns:
            if pat in buf:
                return pat
    return None


def do_login(sock, log_f):
    matched = wait_for(sock, log_f, [b"wish to be known"], timeout=10)
    if matched is None:
        raise ConnectionError("Never got the name prompt from the MUD")
    sock.sendall(USERNAME.encode() + b"\r\n")

    matched = wait_for(sock, log_f, [b"Password:"], timeout=10)
    if matched is None:
        raise ConnectionError("Never got the password prompt from the MUD")
    sock.sendall(PASSWORD.encode() + b"\r\n")

    matched = wait_for(sock, log_f, [b"PRESS RETURN", b"Make your choice"], timeout=10)
    if matched is None:
        raise ConnectionError("Login didn't reach the post-password prompt (bad password?)")
    if matched == b"PRESS RETURN":
        sock.sendall(b"\r\n")
        matched = wait_for(sock, log_f, [b"Make your choice"], timeout=10)
        if matched is None:
            raise ConnectionError("Never reached the character menu")

    sock.sendall(b"1\r\n")  # "Enter the game."
    # Drain the room description that follows so `start` returns useful text.
    wait_for(sock, log_f, [b"Exits:", b">"], timeout=10)


def run_daemon(session_dir):
    p = paths(session_dir)
    log_f = open(p["log"], "ab", buffering=0)

    sock = socket.create_connection((HOST, PORT), timeout=10)
    sock.settimeout(None)

    try:
        do_login(sock, log_f)
    except Exception as e:
        log_f.write(f"\n[LOGIN FAILED: {e}]\n".encode())
        sock.close()
        return

    # Open the FIFO O_RDWR (not O_RDONLY) so the fd never sees EOF just
    # because no writer currently has it open -- otherwise select() would
    # busy-loop reporting "readable" with 0 bytes available.
    fifo_fd = os.open(p["fifo"], os.O_RDWR | os.O_NONBLOCK)

    try:
        while True:
            r, _, _ = select.select([sock, fifo_fd], [], [], 0.5)
            if sock in r:
                data = sock.recv(4096)
                if not data:
                    log_f.write(b"\n[DISCONNECTED]\n")
                    break
                log_f.write(clean(data))
            if fifo_fd in r:
                data = os.read(fifo_fd, 4096)
                if data:
                    for line in data.split(b"\n"):
                        line = line.strip(b"\r")
                        if not line:
                            continue
                        sock.sendall(line + b"\r\n")
    finally:
        os.close(fifo_fd)
        sock.close()
        try:
            os.remove(p["pid"])
        except FileNotFoundError:
            pass


# --------------------------------------------------------------------------
# Client-side subcommands
# --------------------------------------------------------------------------

def cmd_start(args):
    session_dir = args.session_dir
    p = paths(session_dir)

    if is_running(p):
        print(f"Already connected (pid {read_pid(p)}). Use `send`/`read` to interact, or `stop` to end the session.")
        return

    os.makedirs(session_dir, exist_ok=True)
    for key in ("log", "cursor"):
        try:
            os.remove(p[key])
        except FileNotFoundError:
            pass
    open(p["log"], "wb").close()
    with open(p["cursor"], "w") as f:
        f.write("0")

    try:
        os.remove(p["fifo"])
    except FileNotFoundError:
        pass
    os.mkfifo(p["fifo"])

    daemon_log = open(p["daemon_log"], "ab")
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--session-dir", session_dir, "_daemon"],
        stdout=daemon_log,
        stderr=daemon_log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    with open(p["pid"], "w") as f:
        f.write(str(proc.pid))

    # Poll the log until login finishes (in-game prompt or an error banner)
    # or we give up -- either way, print whatever came through.
    deadline = time.time() + 15
    while time.time() < deadline:
        if os.path.exists(p["log"]) and os.path.getsize(p["log"]) > 0:
            with open(p["log"], "rb") as f:
                content = f.read()
            if b"[LOGIN FAILED" in content or b"H " in content and b"V " in content:
                break
        if not pid_alive(proc.pid):
            break
        time.sleep(0.3)

    _print_new(p, advance_cursor=True)


def cmd_send(args):
    p = paths(args.session_dir)
    if not is_running(p):
        print("No active MUD session. Run `mud_client.py start` first.", file=sys.stderr)
        sys.exit(1)
    fd = os.open(p["fifo"], os.O_WRONLY)
    os.write(fd, args.command.encode() + b"\n")
    os.close(fd)
    time.sleep(args.wait)
    _print_new(p, advance_cursor=True)


def cmd_read(args):
    p = paths(args.session_dir)
    if not is_running(p):
        print("No active MUD session. Run `mud_client.py start` first.", file=sys.stderr)
        sys.exit(1)
    if args.wait:
        time.sleep(args.wait)
    _print_new(p, advance_cursor=True)


def cmd_status(args):
    p = paths(args.session_dir)
    running = is_running(p)
    print(f"running: {running}" + (f" (pid {read_pid(p)})" if running else ""))
    if os.path.exists(p["log"]):
        with open(p["log"], "rb") as f:
            f.seek(max(0, os.path.getsize(p["log"]) - 1000))
            print("--- tail of output.log ---")
            print(f.read().decode(errors="replace"))


def cmd_stop(args):
    p = paths(args.session_dir)
    if not is_running(p):
        print("No active session to stop.")
        return
    try:
        fd = os.open(p["fifo"], os.O_WRONLY)
        os.write(fd, b"quit\n0\n")
        os.close(fd)
        time.sleep(1)
    except OSError:
        pass
    pid = read_pid(p)
    if pid and pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
    print("Session stopped.")


def _print_new(p, advance_cursor):
    cursor = 0
    if os.path.exists(p["cursor"]):
        with open(p["cursor"]) as f:
            try:
                cursor = int(f.read().strip())
            except ValueError:
                cursor = 0
    if not os.path.exists(p["log"]):
        return
    with open(p["log"], "rb") as f:
        f.seek(cursor)
        new_data = f.read()
        new_cursor = f.tell()
    sys.stdout.write(new_data.decode(errors="replace"))
    sys.stdout.flush()
    if advance_cursor:
        with open(p["cursor"], "w") as f:
            f.write(str(new_cursor))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session-dir", default=DEFAULT_SESSION_DIR)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("start")

    p_send = sub.add_parser("send")
    p_send.add_argument("command")
    p_send.add_argument("--wait", type=float, default=1.5, help="seconds to wait for a reply before printing")

    p_read = sub.add_parser("read")
    p_read.add_argument("--wait", type=float, default=0.0)

    sub.add_parser("status")
    sub.add_parser("stop")

    p_daemon = sub.add_parser("_daemon")  # internal, spawned by `start`

    args = parser.parse_args()

    if args.subcommand == "_daemon":
        run_daemon(args.session_dir)
    elif args.subcommand == "start":
        cmd_start(args)
    elif args.subcommand == "send":
        cmd_send(args)
    elif args.subcommand == "read":
        cmd_read(args)
    elif args.subcommand == "status":
        cmd_status(args)
    elif args.subcommand == "stop":
        cmd_stop(args)


if __name__ == "__main__":
    main()
