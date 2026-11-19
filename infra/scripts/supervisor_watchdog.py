#!/usr/bin/env python3
"""
Supervisor Watchdog for Cloud Run.

Monitors processes managed by supervisord. If EITHER the Node.js Express backend
or the Python FastAPI AI service exits or enters a FATAL state, this watchdog
immediately signals supervisord to shut down, terminating the container so that
Google Cloud Run can detect container failure and restart or fail over.
"""

import os
import signal
import sys


def write_stdout(msg: str) -> None:
    sys.stdout.write(msg)
    sys.stdout.flush()


def write_stderr(msg: str) -> None:
    sys.stderr.write(msg)
    sys.stderr.flush()


def main() -> None:
    while True:
        # Step 1: Tell supervisor we are ready for events
        write_stdout("READY\n")

        # Step 2: Read event header
        line = sys.stdin.readline()
        if not line:
            break

        try:
            # Header format: ver:3.0 server:supervisor serial:21 pool:watchdog poolserial:21 eventname:PROCESS_STATE_EXITED len:84
            headers = dict(x.split(":", 1) for x in line.split())
            event_len = int(headers.get("len", "0"))
            event_name = headers.get("eventname", "")

            # Step 3: Read event data payload
            payload = sys.stdin.read(event_len)
            data = dict(x.split(":", 1) for x in payload.split())

            process_name = data.get("processname", "unknown")
            expected = data.get("expected", "0")

            write_stderr(
                f"[Supervisor Watchdog] Event '{event_name}' received for process '{process_name}' "
                f"(expected={expected}). Terminating container.\n"
            )

            # Signal parent (supervisord PID 1) to shut down completely
            ppid = os.getppid()
            os.kill(ppid, signal.SIGQUIT)
            break

        except Exception as exc:
            write_stderr(f"[Supervisor Watchdog] Error processing event: {exc}\n")
            try:
                os.kill(os.getppid(), signal.SIGQUIT)
            except OSError:
                pass
            break


if __name__ == "__main__":
    main()
