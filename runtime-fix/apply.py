#!/usr/bin/env python3
"""BR1008L AC runtime IPv6 fix (mode=1): accept_ra=2 + dhcp6pd.conf + cm dhcp6c_get.

Does NOT edit /var/radvd.conf directly.
Requires: Python 3, network reachability to AC Telnet (port 23).
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import socket
import sys
import time


def recv_all(sock: socket.socket, idle: float = 2.0) -> str:
    sock.settimeout(idle)
    chunks: list[bytes] = []
    try:
        while True:
            chunks.append(sock.recv(8192))
            time.sleep(0.05)
    except socket.timeout:
        pass
    return b"".join(chunks).decode("utf-8", "replace")


def run(sock: socket.socket, cmd: str, wait: float = 2.5) -> str:
    sock.sendall((cmd + "\n").encode())
    time.sleep(0.3)
    out = recv_all(sock, wait)
    print(f"\n>>> {cmd}\n{out[-3000:]}")
    return out


def build_pdconf_line(addr: str, plen: int, preferred: int = 604800, valid: int = 2592000) -> str:
    """Format consumed by get_dhcp6_pd: '%s %d %u %u' then 16x %02hhx on the hex field."""
    a = ipaddress.IPv6Address(addr)
    net = ipaddress.IPv6Network((int(a), plen), strict=False)
    p64 = ipaddress.IPv6Network((int(net.network_address), 64), strict=False)
    hex16 = p64.network_address.packed.hex()
    return f"{hex16} 64 {preferred} {valid}"


def enter_debugshell(sock: socket.socket, password: str) -> None:
    recv_all(sock, 1.0)
    sock.sendall((password + "\r\n").encode())
    time.sleep(1.0)
    recv_all(sock, 1.5)
    sock.sendall(b"debugshell\r\n")
    time.sleep(2.0)
    recv_all(sock, 2.0)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="BR1008L AC runtime IPv6 fix (non-persistent)")
    ap.add_argument("--host", default="192.168.124.1", help="AC management IP")
    ap.add_argument("--password", required=True, help="Telnet / admin password")
    ap.add_argument("--port", type=int, default=23)
    args = ap.parse_args()

    sock = socket.create_connection((args.host, args.port), 12)
    try:
        enter_debugshell(sock, args.password)

        run(sock, "echo 2 > /proc/sys/net/ipv6/conf/lan1/accept_ra")
        out = run(sock, "ip -6 addr show lan1")
        m = re.search(r"inet6 ([0-9a-f:]+)/(\d+) scope global", out, re.I)
        if not m:
            print(
                "FAIL: lan1 has no global IPv6 yet.\n"
                "Wait for upstream RA (soft router), ensure accept_ra stuck at 2, retry.",
                file=sys.stderr,
            )
            return 1

        line = build_pdconf_line(m.group(1), int(m.group(2)))
        print(f"PDCONF_LINE={line}")

        # Device busybox often has no printf; echo is enough (spaces OK for fscanf).
        run(sock, f"echo '{line}' > /var/dhcp6pd.conf")
        run(sock, "wc -c /var/dhcp6pd.conf; cat /var/dhcp6pd.conf")
        run(sock, "cm dhcp6c_get; sleep 2", wait=4)

        conf = run(sock, "grep -i -A6 prefix /var/radvd.conf; cat /var/radvd.conf")
        zero = "prefix 0000:0000:0000:0000" in conf
        # Any non-zero looking global-ish prefix line
        ok = (not zero) and bool(re.search(r"prefix\s+[0-9a-f:]+\s*/64", conf, re.I))
        if ok and "240e" in conf.lower():
            print("\n=== OK: radvd.conf contains 240e prefix ===")
        elif ok:
            print("\n=== OK: radvd.conf contains a non-zero prefix ===")
        else:
            print("\n=== FAIL: prefix still missing or zero — see output above ===")
            return 1
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
