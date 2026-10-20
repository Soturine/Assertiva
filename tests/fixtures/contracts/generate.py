import json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from pact import Pact, Verifier, match

out = Path("pacts"); out.mkdir(exist_ok=True)
pact = Pact("orders-web", "pricing-api").with_specification("V4")
(pact.upon_receiving("a member discount").given("a member order of 150.00")
     .with_request("GET", "/discount").with_query_parameters({"total": "15000", "member": "true"})
     .will_respond_with(200).with_body({"discount": match.int(1500)}, content_type="application/json"))
(pact.upon_receiving("an unknown order").given("no order 999")
     .with_request("GET", "/orders/999").will_respond_with(404))
with pact.serve() as srv:
    assert requests.get(f"{srv.url}/discount", params={"total": "15000", "member": "true"}).json()["discount"] == 1500
    assert requests.get(f"{srv.url}/orders/999").status_code == 404
pact.write_file(out, overwrite=True)
empty = Pact("reports-job", "pricing-api").with_specification("V4")
with empty.serve():
    pass
empty.write_file(out, overwrite=True)

def provider(discount):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/discount"):
                body = json.dumps({"discount": discount}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()
        def do_POST(self):  # provider state setup
            self.send_response(200); self.end_headers()
        def log_message(self, *a): pass
    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

for name, discount in (("verified", 1500), ("broken", "1500")):
    server = provider(discount)
    url = f"http://127.0.0.1:{server.server_port}"
    v = Verifier("pricing-api", host="127.0.0.1").add_transport(url=url).add_source(str(out / "orders-web-pricing-api.json"))
    try:
        v.verify(); print(name, "verify ok")
    except Exception as exc:
        print(name, "verify raised", type(exc).__name__)
    Path(f"verification-{name}.json").write_text(json.dumps(v.results, indent=2))
    server.shutdown()
v = Verifier("pricing-api", host="127.0.0.1").add_transport(url="http://127.0.0.1:9").add_source(str(out / "reports-job-pricing-api.json"))
v.set_error_on_empty_pact(enabled=False)
try:
    v.verify(); print("empty verify ok")
except Exception as exc:
    print("empty verify raised", type(exc).__name__)
Path("verification-empty.json").write_text(json.dumps(v.results, indent=2))
