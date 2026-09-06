"""Local HTTP application. Vehicle writes require a reviewed, guarded plan."""
import argparse
import ipaddress
import json
from pathlib import Path
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import webbrowser

from pit import VERSION
from pit.catalog import variant_bundle
from pit.service import PitService, atomic_json

ROOT = Path(__file__).resolve().parent


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, service, lan=False):
        super().__init__(address, Handler)
        self.service = service
        self.csrf = secrets.token_urlsafe(32)
        self.viewer_token = secrets.token_urlsafe(24)
        ips = {"127.0.0.1", "localhost"}
        try:
            ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError:
            pass
        self.allowed_hosts = ips
        self.lan = lan


class Handler(BaseHTTPRequestHandler):
    server_version = "TwizyPitPro"
    def log_message(self, *_):
        pass  # No access logging of the phone token.

    @property
    def local(self):
        return ipaddress.ip_address(self.client_address[0]).is_loopback

    def check_host(self):
        host = urlparse("http://"+self.headers.get("Host", "")).hostname
        return host in self.server.allowed_hosts

    def authorized(self):
        if self.local:
            return True
        token = self.headers.get("X-Pit-Viewer", "")
        return self.server.lan and secrets.compare_digest(token, self.server.viewer_token)

    def respond(self, body, status=200, content_type="application/json; charset=utf-8", attachment=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.check_host():
            return self.respond({"error": "Host geweigerd."}, 403)
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/"):
                if not self.authorized():
                    return self.respond({"error": "Telefoontoken ontbreekt of is ongeldig."}, 401)
                service = self.server.service
                if path == "/api/security/status":
                    return self.respond(dict(password_required=False, local_control_only=True))
                if path == "/api/bootstrap":
                    return self.respond(dict(version=VERSION, local=self.local, csrf=self.server.csrf if self.local else None,
                                             lan=self.server.lan, phone_urls=[f"http://{ip}:{self.server.server_port}/?viewer={self.server.viewer_token}" for ip in self.server.allowed_hosts if ip not in ("localhost", "127.0.0.1")] if self.local and self.server.lan else []))
                if path == "/api/state":
                    return self.respond(service.state())
                if path == "/api/ports":
                    return self.respond(service.ports() if self.local else [])
                if path == "/api/profiles":
                    return self.respond(service.profiles())
                if path == "/api/sessions":
                    return self.respond(service.sessions())
                if path == "/api/download/android":
                    apk = ROOT / "releases" / "android" / "TwizyPitPro-0.3.1.apk"
                    if not apk.is_file():
                        return self.respond({"error": "Android-APK nog niet beschikbaar."}, 404)
                    return self.respond(apk.read_bytes(), content_type="application/vnd.android.package-archive", attachment=apk.name)
                if path == "/api/export/report":
                    return self.respond(service.state(), attachment="twizy-pitrapport.json")
                if path == "/api/export/variants":
                    return self.respond(variant_bundle(), attachment="twizy-versiepakketten.json")
                if path == "/api/export/session":
                    sid = parse_qs(parsed.query).get("id", [""])[0]
                    return self.respond(service.csv_session(sid), content_type="text/csv; charset=utf-8", attachment="twizy-sessie.csv")
                return self.respond({"error": "Onbekend API-pad."}, 404)
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"), "/icon.svg": ("icon.svg", "image/svg+xml"),
                      "/icon.png": ("icon.png", "image/png"), "/icon.ico": ("icon.ico", "image/x-icon"),
                      "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json")}
            if path not in assets:
                return self.respond({"error": "Niet gevonden."}, 404)
            filename, mime = assets[path]
            self.respond((ROOT/"web"/filename).read_bytes(), content_type=mime)
        except (ValueError, OSError) as exc:
            self.respond({"error": str(exc)}, 400)

    def reject_post(self, message, status):
        # Consume only a bounded body on rejected requests. Closing a Windows
        # socket with unread POST bytes can otherwise reset the 403 response.
        previous = self.connection.gettimeout()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if 0 < length <= 200000:
                self.connection.settimeout(1)
                self.rfile.read(length)
        except (ValueError, OSError):
            pass
        finally:
            self.connection.settimeout(previous)
        return self.respond({"error": message}, status)

    def do_POST(self):
        if not self.check_host() or not self.local:
            return self.reject_post("Bediening is alleen toegestaan vanaf deze laptop.", 403)
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        if origin != f"http://{host}" or not secrets.compare_digest(self.headers.get("X-Pit-CSRF", ""), self.server.csrf):
            return self.reject_post("Ongeldige sessie of herkomst.", 403)
        if self.headers.get_content_type() != "application/json":
            return self.reject_post("JSON vereist.", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 200000:
                raise ValueError("Ongeldige aanvraaggrootte.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("JSON-object vereist.")
            service = self.server.service
            routes = {
                "/api/connect": lambda: service.connect(**body),
                "/api/disconnect": lambda: service.disconnect(),
                "/api/diagnose": lambda: service.diagnose(),
                "/api/demo": lambda: service.set_demo(**body),
                "/api/plan": lambda: service.make_plan(body.get("values")),
                "/api/apply-demo": lambda: service.apply_demo(body.get("plan_id")),
                "/api/cycle-demo": lambda: service.demo_cycle(body.get("restore", False)),
                "/api/profile": lambda: service.save_profile(body.get("name"), body.get("values")),
                "/api/record": lambda: service.recording(**body),
                "/api/vehicle/prepare": lambda: service.vehicle_action("prepare", **body),
                "/api/vehicle/snapshot": lambda: service.vehicle_action("snapshot", **body),
                "/api/vehicle/close-access": lambda: service.vehicle_action("close-access", **body),
                "/api/vehicle/apply": lambda: service.vehicle_action("apply", **body),
                "/api/vehicle/restore": lambda: service.vehicle_action("restore", **body),
                "/api/vehicle/restore-plan": lambda: service.vehicle_action("restore-plan", **body),
                "/api/vehicle/verify-cycle": lambda: service.vehicle_action("verify-cycle", **body),
            }
            if self.path not in routes:
                return self.respond({"error": "Deze actie bestaat niet."}, 404)
            result = routes[self.path]()
            if self.path != "/api/plan":
                service.event("Lokale actie uitgevoerd", self.path.removeprefix("/api/"))
            self.respond(result if result is not None else {"ok": True})
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            self.respond({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description="Twizy Pit Pro — standaard demo; vLinker-schrijfplan apart voorbereiden en bevestigen")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--lan", action="store_true", help="Telefoonviewer op lokaal netwerk; alle bediening blijft op laptop")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    service = PitService(ROOT/"data")
    server = Server(("0.0.0.0" if args.lan else "127.0.0.1", args.port), service, args.lan)
    for item in variant_bundle():
        atomic_json(ROOT/"profiles"/f"T{item['model']}-{item['software']}.json", item)
    service.start_worker()
    print(f"Twizy Pit Pro {VERSION} — http://127.0.0.1:{args.port}", flush=True)
    print("DEMO · live verbinden na selectie · schrijven uitsluitend via gecontroleerd vLinker-plan", flush=True)
    if args.open:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop.set()
        server.server_close()
        if service.link:
            service.link.close()


if __name__ == "__main__":
    main()
