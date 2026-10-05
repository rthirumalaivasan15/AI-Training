"""Record the raw JSON-RPC between the host and one stdio MCP server, untouched.

Put it in front of a server's command in an MCP config:

    "command": "python",
    "args": ["wiretap.py", "runs/wire_raw.jsonl", "--", "python", "claims_system/server.py"]

Every line in each direction is forwarded byte for byte and appended to the log
as {"t": seconds since start, "dir": "host->server" | "server->host", "raw": line}.
The server's stderr is passed straight through and not recorded.
"""
import sys
import json
import time
import threading
import subprocess


def main():
    out, sep, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
    assert sep == "--", "usage: wiretap.py LOG -- COMMAND [ARGS...]"
    if cmd[0] in ("python", "python3"):
        cmd[0] = sys.executable
    child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    sink = open(out, "a", encoding="utf-8")
    lock = threading.Lock()
    started = time.perf_counter()

    def record(direction, line):
        with lock:
            sink.write(json.dumps({"t": round(time.perf_counter() - started, 4), "dir": direction,
                                   "raw": line.decode("utf-8").rstrip("\r\n")}) + "\n")
            sink.flush()

    def host_to_server():
        for line in iter(sys.stdin.buffer.readline, b""):
            record("host->server", line)
            child.stdin.write(line)
            child.stdin.flush()
        child.stdin.close()

    threading.Thread(target=host_to_server, daemon=True).start()
    for line in iter(child.stdout.readline, b""):
        record("server->host", line)
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    child.wait()
    sink.close()


if __name__ == "__main__":
    main()
