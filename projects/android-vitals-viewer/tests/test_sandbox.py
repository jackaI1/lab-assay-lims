import re
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from sandbox.server import make_app, PATIENT


def login(client):
    consent = client.get('/auth/login', follow_redirects=True)
    callback = re.search(r'href="([^"]*code=[^"]+)"', consent.text)[1].replace('&amp;', '&')
    assert client.get(callback).json()['authorized'] is True
    return callback


def test_real_bridge_login_report_refresh_and_expiry():
    app = make_app()
    with TestClient(app, base_url='http://localhost:8000') as client:
        route = f'/openemr/patients/{PATIENT}/visits'
        assert client.get(route).status_code == 401
        callback = login(client)
        report = client.get(route).json()
        assert report['synthetic_only'] is True
        assert len(report['visits']) == 2
        assert report['counts'] == {'total': 18, 'assigned': 18, 'unassigned': 0, 'excluded': 0}
        assert {o['code']['coding'][0]['code'] for v in report['visits'] for o in v['observations']} == {'8867-4', '8310-5', '59408-5'}
        session = next(iter(app.state.auth.sessions.values()))
        old_refresh = session.refresh_token
        session.token_expiry = 0
        assert client.get(route).status_code == 200
        assert app.state.sandbox.refresh_count == 1
        assert session.refresh_token != old_refresh
        assert client.get(callback).status_code == 400  # one-use state/code
        client.post('/sandbox/expire')
        assert client.get(route).status_code == 401


def test_denied_login_and_logout():
    with TestClient(make_app(), base_url='http://localhost:8000') as client:
        client.get('/auth/login')
        assert client.get('/auth/callback?error=access_denied').status_code == 400
        assert client.get(f'/openemr/patients/{PATIENT}/visits').status_code == 401
        login(client)
        assert client.post('/auth/logout').status_code == 200
        assert client.get(f'/openemr/patients/{PATIENT}/visits').status_code == 401


def test_forged_state_and_wrong_patient():
    with TestClient(make_app(), base_url='http://localhost:8000') as client:
        client.get('/auth/login')
        assert client.get('/auth/callback?state=forged&code=forged').status_code == 400
        login(client)
        assert client.get('/openemr/patients/22222222-2222-4222-8222-222222222222/visits').status_code == 404


def test_revoked_refresh_requires_login():
    app = make_app()
    with TestClient(app, base_url='http://localhost:8000') as client:
        login(client)
        next(iter(app.state.auth.sessions.values())).token_expiry = 0
        app.state.sandbox.refresh.clear()
        assert client.get(f'/openemr/patients/{PATIENT}/visits').status_code >= 400
        assert client.get(f'/openemr/patients/{PATIENT}/visits').status_code == 401
