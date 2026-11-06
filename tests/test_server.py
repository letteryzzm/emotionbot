import json
import urllib.request

import pytest

from app.server import DashboardServer, StateStore


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, r.read()


def _post(port, path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.status, json.loads(r.read())


@pytest.fixture()
def server():
    store = StateStore()
    calls = {"rest": 0, "expr": None, "say": None}
    srv = DashboardServer(
        store, port=0,
        on_rest=lambda: calls.__setitem__("rest", calls["rest"] + 1),
        on_expression=lambda n, i: calls.__setitem__("expr", (n, i)),
        on_say=lambda t: calls.__setitem__("say", t),
    ).start()
    yield srv, store, calls
    srv.stop()


def test_state_endpoint_serves_snapshot(server):
    srv, store, _ = server
    store.add_event({"t": 1.0, "asr_text": "今天特别开心", "fusion": {"label": "happy"},
                     "per_modality": {}, "expression": {"name": "happy"}, "latency_ms": 12})
    status, body = _get(srv.port, "/api/state")
    assert status == 200
    data = json.loads(body)
    assert data["now"]["asr_text"] == "今天特别开心"
    assert data["history"][0]["fusion"]["label"] == "happy"


def test_dashboard_html_is_served(server):
    srv, _, _ = server
    status, body = _get(srv.port, "/")
    assert status == 200
    assert "EmotionBot".encode("utf-8") in body


def test_control_endpoints_call_back(server):
    srv, _, calls = server
    assert _post(srv.port, "/api/rest", {})[0] == 200
    assert calls["rest"] == 1
    _post(srv.port, "/api/expression", {"name": "concerned", "intensity": 0.8})
    assert calls["expr"] == ("concerned", 0.8)
    _post(srv.port, "/api/say", {"text": "你好"})
    assert calls["say"] == "你好"


def test_unknown_post_returns_404(server):
    srv, _, _ = server
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/api/nope", data=b"{}",
                                 method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=3)
    assert e.value.code == 404


def test_store_history_is_bounded():
    store = StateStore(history=3)
    for i in range(5):
        store.add_event({"t": i, "asr_text": str(i), "fusion": {}, "per_modality": {},
                         "expression": {}, "latency_ms": 0})
    hist = store.snapshot()["history"]
    assert [h["t"] for h in hist] == [2, 3, 4]
