"""Standalone ZMQ probe to isolate where the ``reduced`` stream is lost.

This bypasses ALL pdf-auto reduction code and tests only the beamline ZMQ
transport: a bare Publisher -> proxy -> RemoteDispatcher round-trip using the
exact ``[PUBLISH TO]`` sockets and prefix.

Usage (two terminals, in the pdf-auto pixi env, on the beamline):

    # Terminal A -- SUBSCRIBER, start this FIRST and wait for its banner:
    python scripts/zmq_probe.py sub

    # Terminal B -- PUBLISHER, start AFTER the subscriber banner prints:
    python scripts/zmq_probe.py pub

Interpretation:

- SUB prints "[PROBE-SUB] received ..." lines  -> transport is FINE; the loss
  is inside pdf-auto's wiring (not the proxy).
- SUB prints only its banner, nothing else     -> the publish_host ->
  subscribe_host bridge is NOT delivering (proxy down, wrong socket, or a
  slow-joiner drop). This is the bug to chase.

Override the sockets/prefix from the command line if your config differs:

    python scripts/zmq_probe.py sub  --subscribe ipc:///.../out.sock --prefix reduced
    python scripts/zmq_probe.py pub  --publish   ipc:///.../out.sock --prefix reduced
"""

from __future__ import annotations

import argparse
import time

from bluesky.callbacks.zmq import Publisher, RemoteDispatcher

DEFAULT_PUBLISH = "ipc:///var/lib/bluesky-zmq-proxy/pdf-tcp-in-ipc-out/out.sock"
DEFAULT_SUBSCRIBE = "ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock"
DEFAULT_PREFIX = "reduced"


def run_sub(subscribe_host: str, prefix: bytes) -> None:
    rd = RemoteDispatcher(subscribe_host, prefix=prefix, strict=False)

    def echo(name, doc):
        print(
            f"[PROBE-SUB] received {name}: keys={list(doc)[:6]}",
            flush=True,
        )

    rd.subscribe(echo)
    print(
        f"[PROBE-SUB] subscribed to {subscribe_host} prefix={prefix!r}; waiting...",
        flush=True,
    )
    rd.start()


def run_pub(publish_host: str, prefix: bytes, n: int) -> None:
    pub = Publisher(publish_host, prefix=prefix)
    print(
        f"[PROBE-PUB] connected to {publish_host} prefix={prefix!r}",
        flush=True,
    )
    # Give PUB/SUB time to connect (avoid slow-joiner drop).
    time.sleep(1.0)
    uid = "probe-0001"
    for i in range(n):
        pub("start", {"uid": uid, "probe": True, "n": i})
        pub(
            "stop",
            {"uid": f"{uid}-stop-{i}", "run_start": uid, "exit_status": "success"},
        )
        print(f"[PROBE-PUB] sent start+stop #{i}", flush=True)
        time.sleep(0.5)
    print("[PROBE-PUB] done", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="pdf-auto ZMQ transport probe")
    parser.add_argument("mode", choices=("sub", "pub"))
    parser.add_argument("--publish", default=DEFAULT_PUBLISH)
    parser.add_argument("--subscribe", default=DEFAULT_SUBSCRIBE)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    prefix = args.prefix.encode()
    if args.mode == "sub":
        run_sub(args.subscribe, prefix)
    else:
        run_pub(args.publish, prefix, args.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
