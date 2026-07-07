#!/usr/bin/env python3
"""DEV: drive the in-game WoT REPL (the moe_calculator_debug mod) from the host PC.

The debug mod (tools/dev/mod_moe_calculator_debug.py, packaged as com.14th_ua.moe_calculator_debug.wotmod)
runs a TCP REPL on 127.0.0.1:2224 inside the live client (the research bar's debug REPL
owns 2223). This client sends one
command per line and reads until the server's __WGEND__ sentinel.

  python tools/dev/repl_client.py "<python expr/stmt>"     # single command
  python tools/dev/repl_client.py --file cmds.txt          # one command per line

Notes:
- Each connection is a fresh REPL namespace (state shared only WITHIN one run),
  so put interdependent commands in one --file.
- Multi-line defs/with-blocks do NOT work line-by-line: write them to a .py file
  and run `execfile(r'<abs path>')` (Python 2 builtin) as a single command.
- Run under Python 3 (host). The game side is Python 2.7.
"""
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 2224
SENTINEL = "__WGEND__"


def run(commands, timeout=8.0):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
    s.settimeout(timeout)
    buf = ""

    def read_until_sentinel():
        nonlocal buf
        out = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.rstrip("\r")
                if line == SENTINEL:
                    return "\n".join(out)
                out.append(line)
            try:
                chunk = s.recv(4096).decode("utf-8", "replace")
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
        return "\n".join(out) + "\n[TIMEOUT/partial]"

    results = []
    for cmd in commands:
        s.sendall((cmd + "\n").encode("utf-8"))
        results.append((cmd, read_until_sentinel()))
    try:
        s.close()
    except Exception:
        pass
    return results


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            commands = [l.rstrip("\n") for l in f if l.strip() and not l.lstrip().startswith("#")]
    else:
        commands = [" ".join(sys.argv[1:])]
    try:
        for cmd, res in run(commands):
            print(">>> " + cmd)
            print(res)
            print("-" * 60)
    except (ConnectionRefusedError, OSError) as e:
        print("CONNECT FAILED: %s" % e)
        print("Is WoT running with com.14th_ua.moe_calculator_debug.wotmod, and in the Garage?")
        sys.exit(1)


if __name__ == "__main__":
    main()
