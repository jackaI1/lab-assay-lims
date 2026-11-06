"""Run the real bridge with an in-process, fictional SMART/FHIR upstream.

No upstream account, patient database or external network is used at runtime.
The only HTTP listener is uvicorn on localhost:8000. Ctrl-C closes it.
"""
import base64
import hashlib
import html
import secrets
import time
from urllib.parse import parse_qs, urlencode

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fhir_emr_bridge.app import create_app
from fhir_emr_bridge.config import Settings

PATIENT = "11111111-1111-4111-8111-111111111111"
ORIGIN = "http://localhost:8000"


def resources():
    subject = {"reference": f"Patient/{PATIENT}"}
    patient = {"resourceType": "Patient", "id": PATIENT, "birthDate": "1990-01-01",
               "name": [{"family": "SYNTHETIC", "given": ["FHIRBridgeDemo"]}]}
    encounters, observations = [], []
    for visit, day in [("morning", "15"), ("followup", "16")]:
        encounters.append({"resourceType": "Encounter", "id": visit, "status": "finished",
                           "subject": subject, "period": {"start": f"2025-01-{day}T10:00:00Z"}})
        for code, unit, values in [("8867-4", "/min", [68, 74, 70]),
                                    ("8310-5", "Cel", [36.8, 37.1, 36.9]),
                                    ("59408-5", "%", [98, 97, 99])]:
            for n, value in enumerate(values):
                observations.append({"resourceType": "Observation", "id": f"{visit}-{code}-{n}",
                    "status": "final", "subject": subject, "encounter": {"reference": f"Encounter/{visit}"},
                    "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
                    "effectiveDateTime": f"2025-01-{day}T10:{n * 5:02d}:00Z",
                    "valueQuantity": {"value": value, "code": unit, "system": "http://unitsofmeasure.org"}})
    return patient, encounters, observations


class FictionalUpstream:
    def __init__(self):
        self.codes = {}
        self.access = {}
        self.refresh = set()
        self.refresh_count = 0

    def issue(self):
        token, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.access[token] = time.monotonic() + 15
        self.refresh.add(refresh)
        return {"access_token": token, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 15}

    def handle(self, request):
        path = request.url.path
        if path == "/fhir/.well-known/smart-configuration":
            return httpx.Response(200, json={"authorization_endpoint": ORIGIN + "/sandbox/authorize",
                "token_endpoint": ORIGIN + "/sandbox/token", "code_challenge_methods_supported": ["S256"]})
        if path == "/sandbox/token":
            form = parse_qs(request.content.decode())
            if form.get("client_id") != ["android-vitals-sandbox"]:
                return httpx.Response(401, json={"error": "invalid_client"})
            if form.get("grant_type") == ["authorization_code"]:
                code = form.get("code", [""])[0]
                challenge = self.codes.pop(code, None)
                actual = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", [""])[0].encode()).digest()).rstrip(b"=").decode()
                if not challenge or challenge != actual or form.get("redirect_uri") != [ORIGIN + "/auth/callback"]:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(200, json=self.issue())
            refresh = form.get("refresh_token", [""])[0]
            if refresh not in self.refresh:
                return httpx.Response(400, json={"error": "invalid_grant"})
            self.refresh.remove(refresh)
            self.refresh_count += 1
            return httpx.Response(200, json=self.issue())
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if self.access.get(token, 0) <= time.monotonic():
            return httpx.Response(401, json={"error": "expired"})
        patient, encounters, observations = resources()
        if path == f"/fhir/Patient/{PATIENT}":
            return httpx.Response(200, json=patient)
        kind = path.rsplit("/", 1)[-1]
        if kind in {"Encounter", "Observation"} and request.url.params.get("patient") == PATIENT:
            return httpx.Response(200, json={"resourceType": "Bundle", "type": "searchset",
                "entry": [{"resource": r} for r in (encounters if kind == "Encounter" else observations)]})
        return httpx.Response(404, json={"resourceType": "OperationOutcome"})


def make_app():
    upstream = FictionalUpstream()
    app = create_app(Settings(fhir_base_url=ORIGIN + "/fhir", smart_client_id="android-vitals-sandbox",
        redirect_uri=ORIGIN + "/auth/callback"), transport=httpx.MockTransport(upstream.handle))
    app.state.sandbox = upstream

    @app.get("/sandbox/authorize", response_class=HTMLResponse)
    def consent(request: Request):
        params = request.query_params
        if (params.get("redirect_uri") != ORIGIN + "/auth/callback" or
            params.get("client_id") != "android-vitals-sandbox" or
            params.get("aud") != ORIGIN + "/fhir" or
            params.get("code_challenge_method") != "S256" or not params.get("code_challenge")):
            return HTMLResponse("Invalid authorization request", status_code=400)
        code = secrets.token_urlsafe(32)
        upstream.codes[code] = params["code_challenge"]
        if len(upstream.codes) > 128:
            upstream.codes.pop(next(iter(upstream.codes)))
        callback = ORIGIN + "/auth/callback?" + urlencode({"code": code, "state": params.get("state", "")})
        denied = ORIGIN + "/auth/callback?error=access_denied"
        return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
        <body style="font:20px sans-serif;padding:24px;color:#16324b"><h1>Fictional records sandbox</h1>
        <p>Allow Vitals Viewer to read two visits and 18 measurements for SYNTHETIC, FHIRBridgeDemo?</p>
        <p>No account or real medical information is used.</p>
        <p><a href="{html.escape(callback)}">Approve fictional records</a></p>
        <p><a href="{denied}">Deny access</a></p></body></html>'''

    @app.post("/sandbox/expire")
    def expire():
        # Explicit local test control, never part of the production bridge.
        app.state.auth.sessions.clear()
        upstream.refresh.clear()
        upstream.access.clear()
        return {"expired": True}

    @app.get("/sandbox/status")
    def status():
        return {"fictional": True, "refresh_count": upstream.refresh_count}

    return app


app = make_app()
