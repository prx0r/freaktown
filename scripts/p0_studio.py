#!/usr/bin/env python3
"""P0 studio — watch a sealed minute, press POG when you laugh, submit feedback.

Sealed takes only (Mode A): generation stays CLI (`scripts/build_set.py`,
theory->lines adapter still missing; takes built from p0-sets.json lines
with theory provenance in set_plan.json). This server captures the human
leg: playback-relative reactions per schemas/pog.reaction.v1.json plus a
post-show feedback form as a proxy for YouTube comments/engagement.

Usage:
  python3 scripts/p0_studio.py            # :8091
  python3 scripts/p0_studio.py --port 8091

Stores (gitignored data/, append-only):
  data/p0/reactions.jsonl   one row per press
  data/p0/feedback.jsonl    one row per post-show form
"""

import argparse
import glob
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

app = Flask(__name__)

P0 = HERE / "data" / "p0"
PILOT = HERE / "data" / "pilot-sergeant-sled"
REACT_LOG = P0 / "reactions.jsonl"
FEED_LOG = P0 / "feedback.jsonl"
TOKEN_FILE = HERE / "data" / ".p0_token"
KINDS = ("POG", "HAHA", "CLAP")
VERDICTS = ("KEEP", "CUT")


class PrefixStrip:
    """Serve under a tunnel subpath (e.g. /p0/*) without changing routes.

    Strips a known prefix so local dev (no prefix) and public (/p0)
    both work against the same routes.
    """

    def __init__(self, wsgi, prefix="/p0"):
        self.wsgi = wsgi
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            environ["SCRIPT_NAME"] = self.prefix
        return self.wsgi(environ, start_response)


app.wsgi_app = PrefixStrip(app.wsgi_app)


def _token():
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_hex(16))
        os.chmod(TOKEN_FILE, 0o600)
    return TOKEN_FILE.read_text().strip()


@app.before_request
def _gate():
    # Reads are public (the MP4s already live on the public shows site).
    # Writes carry the backend-held token in a header — never in the URL.
    if request.path in ("/api/p0/react", "/api/p0/feedback"):
        if request.headers.get("X-P0-Token", "") != _token():
            return jsonify({"ok": False, "error": "bad token"}), 401
    return None


def _load_perfs():
    idx = json.load(open(P0 / "performances.json"))
    perfs = list(idx["performances"])
    # Pilot Sled lives outside data/p0/ with a different mp4 name.
    if not any(p.get("set") == "sergeant-sled" for p in perfs):
        perfs.append({"character": "pog.sergeant-sled", "dir": "data/pilot-sergeant-sled",
                      "set": "sergeant-sled", "status": "AUDITIONING",
                      "voice": "pilot", "qa_pass": True})
    return perfs


def _resolve_video(p, ext="mp4"):
    d = HERE / p["dir"]
    base = "sergeant-sled-set" if p["set"] == "sergeant-sled" else "set"
    for cand in (d / f"{base}.{ext}", d / f'{p["set"]}.{ext}'):
        if cand.exists():
            return cand
    if ext == "mp4":
        hits = sorted(glob.glob(str(d / "*.mp4")))
        return Path(hits[0]) if hits else None
    return None


def _first_set():
    for p in _load_perfs():
        if _resolve_video(p):
            return p["set"]
    return "doug-deadline"


def _load_json(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default


def _plan(p):
    return _load_json(HERE / p["dir"] / "set_plan.json", {}) or {}


def _timeline(p):
    tl = _load_json(HERE / p["dir"] / "timeline.json", [])
    return tl if isinstance(tl, list) else []


def _beat_at(timeline, ms):
    for b in timeline:
        start = b.get("start_ms", 0)
        end = b.get("end_ms", start) + b.get("pause_after_ms", 0)
        if start <= ms < end:
            return b.get("beat_id")
    return None


def _read_log(path):
    rows = []
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


INDEX_CSS = ("body{background:#0d0714;color:#f5eeda;font-family:Georgia,serif;margin:0;padding:28px}"
             "a{color:#c9a86a}.card{border:1px solid #3a2a55;border-radius:12px;padding:14px;margin:12px 0}"
             ".meta{color:#cbbfa5;font-size:.9em}button{background:#c9a86a;border:0;border-radius:10px;"
             "padding:14px 26px;font-size:1.2em;font-weight:bold;margin:6px;cursor:pointer}"
             "video{width:100%;max-width:420px;background:#000;border-radius:12px}"
             "textarea,input[type=text]{width:100%;max-width:420px;background:#1a1026;color:#f5eeda;"
             "border:1px solid #3a2a55;border-radius:8px;padding:8px}")


@app.after_request
def _no_store_html(resp):
    if resp.content_type.startswith("text/html"):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.route("/health")
def health():
    return jsonify({"ok": True, "studio": "p0"})


@app.route("/api/p0/sets")
def api_sets():
    out = []
    for p in _load_perfs():
        plan = _plan(p)
        tl = _timeline(p)
        vid = _resolve_video(p)
        out.append({"set": p["set"], "character": p.get("character"),
                    "status": p.get("status"), "voice": p.get("voice"),
                    "qa_pass": p.get("qa_pass"),
                    "premise": plan.get("premise"), "mechanisms": plan.get("mechanisms"),
                    "intent": plan.get("comic_intent"), "lines": plan.get("lines"),
                    "beats": len(tl),
                    "duration_s": p.get("duration_s"),
                    "has_video": bool(vid)})
    return jsonify({"count": len(out), "sets": out})


@app.route("/sets")
def sets_list():
    cards = []
    reacts = _read_log(REACT_LOG)
    feeds = _read_log(FEED_LOG)
    for p in _load_perfs():
        s = p["set"]
        plan = _plan(p)
        n_pog = sum(1 for r in reacts if r.get("set_id") == s and r.get("kind") == "POG")
        n_fb = sum(1 for r in feeds if r.get("set_id") == s)
        premise = plan.get("premise") or "—"
        mechs_raw = plan.get("mechanisms") or []
        mechs = ",".join(mechs_raw.keys() if isinstance(mechs_raw, dict) else mechs_raw) or "—"
        cards.append(
            f'<div class="card"><h2>{s}</h2>'
            f'<div class="meta">{p.get("character")} · {p.get("status")} · '
            f'QA {"PASS" if p.get("qa_pass") else "?"} · {p.get("duration_s", "?")}s · '
            f'{n_pog} POG · {n_fb} feedback</div>'
            f'<p><i>{premise}</i> <span class="meta">[{mechs}]</span></p>'
            f'<a href="/watch/{s}">watch + judge</a> · '
            f'<a href="/api/p0/summary/{s}">summary json</a></div>')
    return (f"<html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<style>{INDEX_CSS}</style></head><body><h1>P0 studio</h1>"
            f"<p>Sealed takes. Watch, press POG when you laugh, submit feedback after. "
            f"Generation stays CLI: <code>scripts/build_set.py --character &lt;id&gt;</code> "
            f"(theory→lines adapter still missing).</p>"
            + "".join(cards) + "</body></html>")


@app.route("/")
def index():
    """The player: big screen, one big POG button, feedback box, submit → next."""
    return (f"<html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<style>{INDEX_CSS}"
            "video{width:min(96vw,1000px);height:auto;max-height:68vh;background:#000;border-radius:14px;display:block;margin:0 auto}"
            ".wrap{max-width:1040px;margin:0 auto;text-align:center}"
            "#pog{width:min(96vw,1000px);font-size:2em;padding:20px}"
            "#comment{width:min(96vw,1000px);min-height:90px;font-size:1.1em}"
            "#send{width:min(96vw,1000px);font-size:1.3em;padding:16px}"
            "#cap{color:#cbbfa5;min-height:1.4em}"
            "</style></head><body><div class=wrap>"
            f"<link href='https://cdn.jsdelivr.net/npm/video.js@8/dist/video-js.min.css' rel='stylesheet'>"
            f"<div id=prog class=meta></div>"
            f"<div id=cap style='font-size:1.4em;margin:12px'></div>"
            f"<video id=v class='video-js vjs-big-play-centered' controls playsinline preload=metadata "
            f"style='width:min(96vw,1000px);height:auto;aspect-ratio:9/16;background:#000;margin:0 auto'></video>"
            f"<div class=meta><a id=openbtn href='#'>open in system player</a> · "
            f"<a href='#' onclick='sync();return false'>sync clock</a></div>"
            f"<div id=clock class=meta></div>"
            f"<script src='https://cdn.jsdelivr.net/npm/video.js@8/dist/video.min.js'></script>"
            f"<div id=cap></div>"
            f"<button id=pog onclick='pog()'>POG 😂</button>"
            f"<textarea id=comment placeholder='what landed, what died...'></textarea><br>"
            f"<button id=send onclick='sendfb()'>Submit → next</button>"
            f"<div id=status class=meta></div>"
            f"</div><script>"
            f"let ORDER=[],CUR='',JUDGED=[],T0=null;"
            f"try{{JUDGED=JSON.parse(localStorage.getItem('p0_judged')||'[]');}}catch(e){{}}"
            f"const H={{'Content-Type':'application/json','X-P0-Token':TOK_PLACEHOLDER}};"
            f"const P=location.pathname.startsWith('/p0')?'/p0':'';"
            f"async function boot(){{const j=await (await fetch(P+'/api/p0/sets')).json();"
            f"ORDER=j.sets.filter(s=>s.has_video);"
            f"CUR=(ORDER.find(s=>!JUDGED.includes(s.set))||ORDER[0]).set;load(CUR);}}"
            f"function load(s){{CUR=s;"
            f"document.getElementById('openbtn').href=P+'/media/'+s+'/video';"
            f"player.src([{{src:P+'/media/'+s+'/hls/index.m3u8',type:'application/x-mpegURL'}},"
            f"{{src:P+'/media/'+s+'/video',type:'video/mp4'}}]);"
            f"document.getElementById('comment').value='';"
            f"document.getElementById('clock').textContent='';"
            f"const m=ORDER.find(x=>x.set===s);"
            f"document.getElementById('cap').textContent=(m?m.character+' · ':'')+(m&&m.premise?m.premise:'');"
            f"document.getElementById('prog').textContent=(ORDER.findIndex(x=>x.set===s)+1)+' / '+ORDER.length;"
            f"document.getElementById('status').textContent='';}}"
            f"function sync(){{T0=Date.now();"
            f"document.getElementById('clock').textContent='synced — clock running';"
            f"setInterval(()=>{{if(T0)document.getElementById('clock').textContent='▶ '+(Math.round((Date.now()-T0)/100)/10).toFixed(1)+'s';}},100);}}"
            f"var player=videojs('v',{{fluid:false}});"
            f"async function pog(){{var ms;"
            f"try{{ms=Math.round(player.currentTime()*1000);}}catch(e){{ms=null;}}"
            f"if(!(ms>0)){{if(!T0){{document.getElementById('status').textContent='press play first (or SYNC for system player)';return;}}ms=Date.now()-T0;}}"
            f"const r=await fetch(P+'/api/p0/react',{{method:'POST',headers:H,"
            f"body:JSON.stringify({{set_id:CUR,kind:'POG',playback_ms:ms,viewer:'human-1'}})}});"
            f"document.getElementById('status').textContent=(await r.json()).ok?('POG @ '+(ms/1000).toFixed(1)+'s ✓'):'press failed';}}"
            f"async function sendfb(){{const c=document.getElementById('comment').value;"
            f"await fetch(P+'/api/p0/feedback',{{method:'POST',headers:H,"
            f"body:JSON.stringify({{set_id:CUR,viewer:'human-1',comment:c}})}});"
            f"if(!JUDGED.includes(CUR)){{JUDGED.push(CUR);localStorage.setItem('p0_judged',JSON.stringify(JUDGED));}}"
            f"const rest=ORDER.filter(s=>!JUDGED.includes(s.set));"
            f"if(!rest.length){{document.getElementById('status').textContent='all '+ORDER.length+' judged — looping back';JUDGED=[];localStorage.setItem('p0_judged','[]');load(ORDER[0].set);return;}}"
            f"load(rest[0].set);window.scrollTo(0,0);}}"
            f"document.addEventListener('keydown',e=>{{if(e.key==='p'&&document.activeElement.tagName!=='TEXTAREA')pog();}});"
            f"boot();"
            f"</script></body></html>".replace("TOK_PLACEHOLDER", "'" + _token() + "'"))


@app.route("/watch/<set_id>")
def watch(set_id):
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return "unknown set", 404
    p = perfs[set_id]
    plan = _plan(p)
    beats = _timeline(p)
    beat_list = "".join(
        f"<li><b>{b.get('beat_id')}</b> [{b.get('type')}] {b.get('text','')[:90]}</li>"
        for b in beats)
    return (f"<html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<style>{INDEX_CSS}</style></head><body>"
            f"<p><a href='/'>← all sets</a></p><h1>{set_id}</h1>"
            f"<p class=meta>{p.get('character')} · premise: <i>{plan.get('premise','—')}</i></p>"
            f"<video id=v controls preload=metadata src='/media/{set_id}/video'></video>"
            f"<div><label class=meta>viewer <input type=text id=viewer value=human-1></label></div>"
            f"<div><button onclick=\"press('POG')\">POG 😂</button>"
            f"<button onclick=\"press('HAHA')\">HAHA</button>"
            f"<button onclick=\"press('CLAP')\">CLAP 👏</button></div>"
            f"<div id=status class=meta></div>"
            f"<h3>Post-show feedback (proxy for YT comments + engagement)</h3>"
            f"<textarea id=comment rows=3 placeholder='comment — what landed, what died'></textarea><br>"
            f"<label class=meta>funniest moment (seconds) <input type=text id=funny value=''></label><br>"
            f"<label class=meta><input type=checkbox id=replay> would replay</label> "
            f"<label class=meta><input type=checkbox id=share> would share</label> "
            f"<label class=meta><input type=checkbox id=more> want more of this character</label><br>"
            f"<label class=meta>verdict <select id=verdict><option value=''>—</option>"
            f"<option>KEEP</option><option>CUT</option></select></label> "
            f"<button onclick='sendfb()'>submit feedback</button>"
            f"<h3>Beats ({len(beats)})</h3><ol class=meta>{beat_list}</ol>"
            f"<script>const S='{set_id}';const TOK='{_token()}';const P=location.pathname.startsWith('/p0')?'/p0':'';"
            f"const v=document.getElementById('v');"
            f"const H={{'Content-Type':'application/json','X-P0-Token':TOK}};"
            f"async function press(k){{const ms=Math.round(v.currentTime*1000);"
            f"const r=await fetch(P+'/api/p0/react',{{method:'POST',headers:H,"
            f"body:JSON.stringify({{set_id:S,kind:k,playback_ms:ms,viewer:document.getElementById('viewer').value||'human-1'}})}});"
            f"const j=await r.json();"
            f"document.getElementById('status').textContent=k+' @ '+(ms/1000).toFixed(1)+'s → '+(j.beat_id||'between beats');}}"
            f"async function sendfb(){{const f=parseFloat(document.getElementById('funny').value);"
            f"const r=await fetch(P+'/api/p0/feedback',{{method:'POST',headers:H,"
            f"body:JSON.stringify({{set_id:S,viewer:document.getElementById('viewer').value||'human-1',"
            f"comment:document.getElementById('comment').value,"
            f"funniest_ms:isNaN(f)?null:Math.round(f*1000),"
            f"replay_intent:document.getElementById('replay').checked,"
            f"share_intent:document.getElementById('share').checked,"
            f"want_more:document.getElementById('more').checked,"
            f"verdict:document.getElementById('verdict').value||null}})}});"
            f"document.getElementById('status').textContent=(await r.json()).ok?'feedback saved ✓':'feedback failed';}}"
            f"</script></body></html>")


@app.route("/media/<set_id>/video")
def media_video(set_id):
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return "unknown set", 404
    vid = _resolve_video(perfs[set_id])
    if not vid:
        return "no video", 404
    return send_from_directory(str(vid.parent), vid.name, mimetype="video/mp4")


@app.route("/media/<set_id>/webm")
def media_webm(set_id):
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return "unknown set", 404
    vid = _resolve_video(perfs[set_id], "webm")
    if not vid:
        return "no webm yet", 404
    return send_from_directory(str(vid.parent), vid.name, mimetype="video/webm")


@app.route("/media/<set_id>/hls/<fname>")
def media_hls(set_id, fname):
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    if not re.fullmatch(r"(index\.m3u8|seg\d+\.ts)", fname or ""):
        return "bad file", 400
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return "unknown set", 404
    d = HERE / perfs[set_id]["dir"] / "hls"
    if not (d / fname).exists():
        return "no hls yet", 404
    mime = "application/vnd.apple.mpegurl" if fname.endswith(".m3u8") else "video/mp2t"
    return send_from_directory(str(d), fname, mimetype=mime)


@app.route("/media/<set_id>/poster")
def media_poster(set_id):
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return "unknown set", 404
    d = HERE / perfs[set_id]["dir"]
    if (d / "poster.png").exists():
        return send_from_directory(str(d), "poster.png", mimetype="image/png")
    return "no poster", 404


@app.route("/api/p0/react", methods=["POST"])
def api_react():
    """One laugh press. Conforms to schemas/pog.reaction.v1.json."""
    data = request.json or {}
    set_id = re.sub(r"[^a-z0-9_-]", "", str(data.get("set_id", "")))[:45]
    kind = str(data.get("kind", "")).upper()
    viewer = re.sub(r"[^a-z0-9_-]", "", str(data.get("viewer", "human-1")))[:40] or "human-1"
    try:
        playback_ms = int(data.get("playback_ms", -1))
    except (TypeError, ValueError):
        playback_ms = -1
    perfs = {p["set"]: p for p in _load_perfs()}
    if not set_id or set_id not in perfs or kind not in KINDS or playback_ms < 0:
        return jsonify({"ok": False, "error": "bad reaction"}), 400
    origin = str(data.get("origin", "audience"))
    if origin not in ("audience", "rehearsal"):
        origin = "audience"
    beat_id = _beat_at(_timeline(perfs[set_id]), playback_ms)
    row = {"set_id": set_id, "viewer": viewer, "kind": kind,
           "playback_ms": playback_ms, "wall_ms": int(time.time() * 1000),
           "origin": origin, "beat_id": beat_id}
    with open(REACT_LOG, "a") as f:
        f.write(json.dumps(row) + "\n")
    return jsonify({"ok": True, "beat_id": beat_id})


@app.route("/api/p0/feedback", methods=["POST"])
def api_feedback():
    """Post-show form: comment ~(YT comment), intents ~(engagement), verdict."""
    data = request.json or {}
    set_id = re.sub(r"[^a-z0-9_-]", "", str(data.get("set_id", "")))[:45]
    viewer = re.sub(r"[^a-z0-9_-]", "", str(data.get("viewer", "human-1")))[:40] or "human-1"
    perfs = {p["set"]: p for p in _load_perfs()}
    verdict = data.get("verdict")
    if not set_id or set_id not in perfs or (verdict not in VERDICTS and verdict is not None):
        return jsonify({"ok": False, "error": "bad feedback"}), 400
    try:
        funny = data.get("funniest_ms")
        funny = None if funny is None else int(funny)
    except (TypeError, ValueError):
        funny = None
    row = {"set_id": set_id, "viewer": viewer,
           "wall_ms": int(time.time() * 1000),
           "comment": str(data.get("comment", ""))[:2000],
           "funniest_ms": funny,
           "replay_intent": bool(data.get("replay_intent", False)),
           "share_intent": bool(data.get("share_intent", False)),
           "want_more": bool(data.get("want_more", False)),
           "verdict": verdict}
    with open(FEED_LOG, "a") as f:
        f.write(json.dumps(row) + "\n")
    return jsonify({"ok": True})


@app.route("/api/p0/summary/<set_id>")
def api_summary(set_id):
    """Aggregate human evidence per set. Rates only — never invents L."""
    set_id = re.sub(r"[^a-z0-9_-]", "", set_id)[:45]
    perfs = {p["set"]: p for p in _load_perfs()}
    if set_id not in perfs:
        return jsonify({"ok": False}), 404
    tl = _timeline(perfs[set_id])
    reacts = [r for r in _read_log(REACT_LOG) if r.get("set_id") == set_id]
    feeds = [r for r in _read_log(FEED_LOG) if r.get("set_id") == set_id]
    viewers = sorted({r.get("viewer") for r in reacts} | {r.get("viewer") for r in feeds})
    by_kind: dict = {}
    by_beat: dict = {}
    for r in reacts:
        by_kind[r.get("kind")] = by_kind.get(r.get("kind"), 0) + 1
        b = r.get("beat_id") or "between"
        by_beat[b] = by_beat.get(b, 0) + 1
    pog_by_beat = {}
    for r in reacts:
        if r.get("kind") == "POG":
            b = r.get("beat_id") or "between"
            pog_by_beat[b] = pog_by_beat.get(b, 0) + 1
    strong = sorted([b for b, n in pog_by_beat.items() if n >= 2])
    weak = sorted([b.get("beat_id") for b in tl
                   if b.get("beat_id") not in pog_by_beat])
    eligible = len([v for v in viewers if any(
        f.get("viewer") == v for f in feeds)])
    return jsonify({
        "ok": True, "set_id": set_id,
        "presses": len(reacts), "by_kind": by_kind, "laugh_curve": by_beat,
        "viewers": viewers, "eligible_views": eligible,
        "strong_bits": strong, "weak_bits": weak,
        "feedback": feeds,
        "notebook_facts": {"status": "human evidence" if reacts else "rehearsal only, no audience",
                           "presses": len(reacts), "eligible_views": eligible,
                           "strong_bits": strong, "weak_bits": weak},
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    a = ap.parse_args()
    app.run(host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
