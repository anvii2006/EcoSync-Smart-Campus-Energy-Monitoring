"""Run the EcoSync API with SQLite on the loopback interface."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from api import MAX_BODY, handle, reply
from energy import EnergyService
from sqlite_store import SQLiteStore


DEFAULT_DB = Path(__file__).resolve().parents[1] / "ecosync.sqlite3"
LOCAL_TOKEN = "ecosync-local-demo"
LOCAL_ORIGIN = "http://127.0.0.1:5173"


def make_server(host, port, service, token, origin):
    class Request(BaseHTTPRequestHandler):
        def dispatch(self):
            try:
                url = urlsplit(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0:
                    raise ValueError
                query = dict(parse_qsl(url.query, keep_blank_values=True, max_num_fields=20))
                if length > MAX_BODY:
                    response = reply(413, {"error": "Request body exceeds 4 KiB."}, origin)
                else:
                    response = handle(
                        service, token, origin, self.command, url.path, query,
                        dict(self.headers), self.rfile.read(length) if length else b"",
                    )
            except ValueError:
                response = reply(400, {"error": "Invalid request parameters."}, origin)
            except Exception:
                logging.exception("Unhandled local API error")
                response = reply(500, {"error": "Internal API error."}, origin)
            status, headers, body = response
            payload = body.encode()
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            if status != 204:
                self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_OPTIONS = do_PATCH = do_DELETE = dispatch

        def log_message(self, fmt, *args):
            if getattr(self, "command", "") in {"POST", "PUT"} or args[1] not in ("200", "204"):
                super().log_message(fmt, *args)

    return ThreadingHTTPServer((host, port), Request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    store = SQLiteStore(args.db)
    with make_server("127.0.0.1", args.port, EnergyService(store, "local"),
                     os.getenv("ECOSYNC_TOKEN", LOCAL_TOKEN),
                     os.getenv("ECOSYNC_ALLOWED_ORIGIN", LOCAL_ORIGIN)) as server:
        print(f"EcoSync local API · http://127.0.0.1:{server.server_port} · SQLite: {args.db}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            store.close()


if __name__ == "__main__":
    main()
