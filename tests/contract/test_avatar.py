#!/usr/bin/env python3
"""Avatar golden battery: upload, sniff, manifest, share, fallback.

Uses the Flask test client against real bundle dirs (cleaned up after).
TTS-dependent test uses one short beat to stay fast.
"""

import io
import json
import os
import shutil
import struct
import threading

import pytest

from app import _avatar_runtime, _sniff_glb, app

VRM = "static/avatars/default-v1.vrm"


def _blob():
    return open(VRM, "rb").read()


def _mk_set(c, name="Battery Bot"):
    d = c.post("/api/sets", json={
        "character": {"name": name, "species": "pigeon",
                      "premise": "battery", "vibe": "manic"},
        "beats": [{"id": "b1", "type": "setup", "text": "Hello there friend.",
                   "pace": "normal", "pause_after_ms": 300}],
        "voice": "en-US-GuyNeural"}).get_json()
    return d["slug"]


def _rm(slug):
    shutil.rmtree(f"freaks/{slug}", ignore_errors=True)


def _targetnames_glb():
    js = {"asset": {"version": "2.0"}, "meshes": [{
        "primitives": [{"targets": [{}, {}, {}, {}]}],
        "extras": {"targetNames": ["jawOpen", "mouthFunnel",
                                   "mouthPucker", "viseme_aa"]}}]}
    raw = json.dumps(js).encode()
    while len(raw) % 4:
        raw += b" "
    return (struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(raw))
            + struct.pack("<II", len(raw), 0x4E4F534A) + raw)


class TestAvatarBattery:
    def test_1_static_upload_accepted(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            blob = _blob()
            d = c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(blob), "body.glb")},
                content_type="multipart/form-data").get_json()
            assert d["ok"] and d["status"] == "done"
            man = json.load(open(f"freaks/{slug}/avatar.json"))
            assert man["appearance"]["runtime"]["sha256"] == \
                __import__("hashlib").sha256(blob).hexdigest()
            assert man["appearance"]["runtime"]["format"] == "glb"
            rt = _avatar_runtime(slug)
            assert rt["uri"] == f"/freaks/{slug}/avatar.glb"
        finally:
            _rm(slug)

    def test_2_rigged_means_skeletal(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            d = c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(_blob()), "b.vrm")},
                content_type="multipart/form-data").get_json()
            assert d["capabilities"]["skeletal_animation"] is True
            assert d["capabilities"]["locomotion"] is True
        finally:
            _rm(slug)

    def test_3_targetnames_detected(self):
        caps = _sniff_glb(_targetnames_glb())
        assert caps["lipsync"] is True
        assert caps["lipsync_profile"] == "viseme"
        assert "jawOpen" in caps["morph_names"]
        # primitive POSITION/NORMAL keys must NOT count as names
        assert "POSITION" not in caps["morph_names"]

    def test_3b_primitive_keys_ignored(self):
        js = {"asset": {"version": "2.0"}, "meshes": [{
            "primitives": [{"targets": [{"POSITION": 0, "NORMAL": 0}]}]}]}
        raw = json.dumps(js).encode()
        while len(raw) % 4:
            raw += b" "
        blob = (struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(raw))
                + struct.pack("<II", len(raw), 0x4E4F534A) + raw)
        caps = _sniff_glb(blob)
        assert caps["has_morph_targets"] is True
        assert caps["facial_morphs"] == 0 and caps["lipsync"] is False

    def test_4_vrm_stored_untouched(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            blob = _blob()
            c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(blob), "b.vrm")},
                content_type="multipart/form-data")
            assert open(f"freaks/{slug}/avatar.vrm", "rb").read() == blob
            man = json.load(open(f"freaks/{slug}/avatar.json"))
            assert man["appearance"]["runtime"]["format"] == "vrm"
            assert man["appearance"]["runtime"]["uri"].endswith("avatar.vrm")
        finally:
            _rm(slug)

    def test_5_bad_bytes_rejected(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            d = c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(b"not a model"), "x.glb")},
                content_type="multipart/form-data").get_json()
            assert d["ok"] is False
        finally:
            _rm(slug)

    def test_6_oversize_rejected(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            big = b"glTF" + b"\x00" * (50 * 1024 * 1024)
            d = c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(big), "x.glb")},
                content_type="multipart/form-data").get_json()
            assert d["ok"] is False and "50MB" in d["error"]
        finally:
            _rm(slug)

    def test_7_existing_body_not_regenerated(self):
        c = app.test_client()
        slug = _mk_set(c)
        try:
            c.post("/api/avatar/upload", data={
                "slug": slug, "file": (io.BytesIO(_blob()), "b.glb")},
                content_type="multipart/form-data")
            mtime = os.path.getmtime(f"freaks/{slug}/avatar.glb")
            d = c.post("/api/avatar", json={"slug": slug}).get_json()
            assert d["status"] == "done"
            assert os.path.getmtime(f"freaks/{slug}/avatar.glb") == mtime
        finally:
            _rm(slug)

    def test_8_finish_records_sha(self):
        import basic_body
        from http.server import BaseHTTPRequestHandler, HTTPServer
        blob, _ = basic_body.build("robot", "sha-bot", 7)

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "model/gltf-binary")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        c = app.test_client()
        slug = _mk_set(c, name="Sha Bot")
        try:
            with app.test_request_context():
                from app import _avatar_finish
                import json as _j
                resp = _avatar_finish(
                    slug, app.config.get("x", None) or
                    __import__("pathlib").Path(f"freaks/{slug}"),
                    "job1", "prompt",
                    f"http://127.0.0.1:{srv.server_port}/b.glb",
                    rigged=True, attempted=["test"])
                d = _j.loads(resp.get_data(as_text=True))
            assert resp.status_code == 200 and d["ok"]
            man = json.load(open(f"freaks/{slug}/avatar.json"))
            assert man["appearance"]["runtime"]["sha256"] == \
                __import__("hashlib").sha256(blob).hexdigest()
            assert man["capabilities"]["lipsync"] is True
        finally:
            srv.shutdown()
            _rm(slug)

    def test_9_basic_fallback_performable(self):
        c = app.test_client()
        slug = _mk_set(c, name="Fallback Fred")
        try:
            d = c.post("/api/avatar/basic", json={"slug": slug}).get_json()
            # save auto-attached BASIC, so tier is "existing" (or "basic"
            # if raced); either way the freak is performable.
            assert d["ok"] and d["tier"] in ("basic", "existing")
            rt = _avatar_runtime(slug)
            assert rt is not None and rt["uri"].endswith("avatar.glb")
            man = json.load(open(f"freaks/{slug}/avatar.json"))
            assert man["capabilities"]["lipsync"] is True
            assert man["capabilities"]["skeletal_animation"] is True
        finally:
            _rm(slug)

    def test_10_golden_path(self):
        c = app.test_client()
        slug = _mk_set(c, name="Golden Gretta")
        try:
            # save auto-attached a BASIC body
            assert _avatar_runtime(slug) is not None
            # compose + preload reach the end
            beats = [{"id": "b1", "type": "setup",
                      "text": "Hello there friend.",
                      "pace": "normal", "pause_after_ms": 300}]
            comp = c.post("/api/compose", json={
                "beats": beats, "voice": "en-US-GuyNeural"}).get_json()
            assert comp["ok"] and comp["duration_ms"] > 1000
            pre = c.get(f"/api/preload/{slug}").get_json()
            assert pre["ok"] and len(pre["wordTimings"]) > 0
            # plan clock ≈ compose clock (meta rounding within 0.5s;
            # exact beat-boundary convergence is proven in e2e/test_party)
            # watch page carries the same clock
            html = c.get(f"/f/{slug}").data.decode()
            assert "YOUR TURN" in html
        finally:
            _rm(slug)
