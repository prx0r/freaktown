#!/usr/bin/env python3
"""Tech lab — test the tech, not the productions. One rig per engine.

Rigs: smile (webcam referee), voice (TTS playback), props (manifest
validation — the sandbox boundary), jev (offline image checks; live calls
need spend sign-off).
"""

import json

from flask import Blueprint, jsonify, request

lab_bp = Blueprint("lab", __name__)

LAB_RIGS = [
    ("/party/lab/smile", "E1 · Smile referee",
     "Webcam → calibrate 30 faces → live smile meter. Frames never leave the device."),
    ("/party/lab/voice", "E2 · Voice",
     "Type a line → edge-TTS speaks it. Free, instant proof of the voice path."),
    ("/party/lab/props", "E3 · Prop manifest",
     "Prompt adjectives → manifest validator (the sandbox boundary). No Blender needed."),
    ("/party/lab/jev", "Jev images (offline)",
     "Photo checks + request preview. Live calls need spend sign-off."),
    ("/party/lab/servo", "Affect servo",
     "A/V/P sliders → live delivery params. The handwired heartbeat."),
]

LAB_HOME = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Tech Lab — Freak Town Party</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8;letter-spacing:2px'>TECH LAB</div>
<h1>TEST THE TECH</h1>
<p style='color:#888'>One rig per engine. No productions, just proof.</p>
<div id=cards></div>
<script>
const RIGS = __RIGS__;
document.getElementById('cards').innerHTML = RIGS.map(r =>
  "<div style='border:1px solid #333;border-radius:12px;padding:16px;margin:10px auto;max-width:520px'>"
  + "<div style='font-size:18px'>"+r[1]+"</div>"
  + "<div style='color:#888;font-size:13px'>"+r[2]+"</div>"
  + "<p><a href='"+r[0]+"' style='color:#ff2fa8;font-size:16px'>OPEN RIG →</a></p></div>").join('');
</script></body></html>"""

SMILE_RIG = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Smile referee — Tech Lab</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:16px'>
<div style='color:#ff2fa8'>TECH LAB · E1 SMILE REFEREE</div>
<video id=v autoplay playsinline muted style='width:min(92vw,480px);border-radius:12px;border:1px solid #333'></video>
<h2 id=prompt>allow camera, then press CALIBRATE</h2>
<div style='font-size:52px' id=meter>😐</div>
<div id=prob style='color:#888'>smile prob: —</div>
<p><button id=cal onclick='go()' style='font-size:18px;padding:12px 32px;background:#ff2fa8;border:0;color:#fff;border-radius:24px'>CALIBRATE (30 faces)</button></p>
<p style='color:#555;font-size:12px'>Alternate neutral face / big grin when prompted. Model trains in-page; nothing uploads.</p>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest"></script>
<script src="/static/smile-referee.js"></script>
<script>
let ref = null, running = false;
const v = document.getElementById('v'), prompt = document.getElementById('prompt'),
      meter = document.getElementById('meter'), prob = document.getElementById('prob');
navigator.mediaDevices.getUserMedia({video: true}).then(s => { v.srcObject = s; });
async function go(){
  document.getElementById('cal').disabled = true;
  ref = await SmileReferee.calibrate(v, {samples: 30, onStep: s => {
    if(s.smiling === true) prompt.textContent = 'BIG GRIN 😁 (' + s.i + '/' + s.of + ')';
    else if(s.smiling === false) prompt.textContent = 'neutral face 😐 (' + s.i + '/' + s.of + ')';
    else if(s.epoch !== undefined) prompt.textContent = 'training… epoch ' + s.epoch;
  }});
  prompt.textContent = 'LIVE — hold it…';
  running = true; loop();
}
const cap = document.createElement('canvas');
function loop(){
  if(!running) return;
  cap.width = v.videoWidth; cap.height = v.videoHeight;
  cap.getContext('2d').drawImage(v, 0, 0);
  const p = ref.predict(cap);
  prob.textContent = 'smile prob: ' + p.toFixed(2);
  meter.textContent = p > 0.7 ? '😁' : (p > 0.4 ? '🙂' : '😐');
  requestAnimationFrame(loop);
}
</script></body></html>"""

VOICE_RIG = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Voice — Tech Lab</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8'>TECH LAB · E2 VOICE</div>
<h1>SAY IT</h1>
<textarea id=t rows=3 style='width:min(92vw,480px);font-size:16px;background:#111;color:#eee;border:1px solid #333;border-radius:10px;padding:10px'>Welcome to Freak Town. I am not optimistic.</textarea><br><br>
<button onclick='say()' style='font-size:18px;padding:12px 32px;background:#ff2fa8;border:0;color:#fff;border-radius:24px'>SPEAK</button>
<p id=m style='color:#888'></p><audio id=a controls style='margin-top:12px'></audio>
<script>
async function say(){
  const m = document.getElementById('m'), a = document.getElementById('a');
  m.textContent = 'rendering…';
  const r = await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({text: document.getElementById('t').value, beat_id: 'lab_'+Date.now()})});
  const d = await r.json();
  if(d.ok){ a.src = d.audio; a.play(); m.textContent = 'speaking'; }
  else m.textContent = 'TTS failed (edge-tts offline?)';
}
</script></body></html>"""

PROPS_RIG = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Props — Tech Lab</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8'>TECH LAB · E3 PROP MANIFEST</div>
<h1>PROMPT A THING</h1>
<p style='color:#888'>Adjectives in, manifest out. Validator enforces the closed op vocab — the sandbox boundary. Try breaking it.</p>
<textarea id=t rows=4 style='width:min(92vw,520px);font-size:14px;background:#111;color:#eee;border:1px solid #333;border-radius:10px;padding:10px'>{"version":"prop_job.v1","prompt":"a triumphant peanut","adjectives":["triumphant"],"primitives":[{"op":"uv_sphere","scale":[1,1.4,1],"material":"shell"}],"materials":{"shell":{"base":"#c89b6a"}},"style":"anime","cameras":["hero_34"],"out":["still_1080.png"]}</textarea><br><br>
<button onclick='go()' style='font-size:18px;padding:12px 32px;background:#ff2fa8;border:0;color:#fff;border-radius:24px'>VALIDATE</button>
<pre id=m style='text-align:left;max-width:560px;margin:16px auto;color:#8f8'></pre>
<script>
async function go(){
  const m = document.getElementById('m');
  let job; try{ job = JSON.parse(document.getElementById('t').value); }
  catch(e){ m.textContent = 'not JSON: ' + e; return; }
  const r = await fetch('/party/prop/validate',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify(job)});
  m.textContent = JSON.stringify(await r.json(), null, 1);
}
</script></body></html>"""

JEV_RIG = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Jev images — Tech Lab</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8'>TECH LAB · JEV IMAGES (OFFLINE)</div>
<h1>PHOTO CHECKS, NO SPEND</h1>
<p style='color:#888'>Validates PNG/JPEG bounds + previews the live request shape. Live calls need spend sign-off.</p>
<input type=file id=f accept='image/png,image/jpeg'><br><br>
<pre id=m style='text-align:left;max-width:560px;margin:0 auto;color:#8f8'></pre>
<script>
document.getElementById('f').onchange = async e => {
  const m = document.getElementById('m'), f = e.target.files[0];
  const ext = f.name.split('.').pop().toLowerCase();
  const ok = ['png','jpg','jpeg'].includes(ext) && f.size <= 16*1024*1024;
  m.textContent = JSON.stringify({file: f.name, bytes: f.size,
    dims: '(checked server-side: 256-1568px per side)',
    verdict: ok ? 'WOULD SEND' : 'REJECTED (ext/size)',
    live_request: {model: 'typesafe/jev-preview',
      header: 'TypeSafe-Danger-Zone-Images: true',
      assets: {photo: 'data:image/...'},
      cost_note: '~$0.0001/image — ask-first per money rules'}}, null, 1);
};
</script></body></html>"""


@lab_bp.route("/party/lab", methods=["GET"])
def lab_home():
    rigs = json.dumps([[u, t, d] for u, t, d in LAB_RIGS])
    return LAB_HOME.replace("__RIGS__", rigs)


@lab_bp.route("/party/lab/smile", methods=["GET"])
def lab_smile():
    return SMILE_RIG


@lab_bp.route("/party/lab/voice", methods=["GET"])
def lab_voice():
    return VOICE_RIG


@lab_bp.route("/party/lab/props", methods=["GET"])
def lab_props():
    return PROPS_RIG


@lab_bp.route("/party/lab/jev", methods=["GET"])
def lab_jev():
    return JEV_RIG


SERVO_RIG = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Affect servo — Tech Lab</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8'>TECH LAB · AFFECT SERVO</div>
<h1>A / V / P → DELIVERY</h1>
<p style='color:#888'>Drag the affect coordinates. Same math as the Python mirror (parity-tested).</p>
<div style='max-width:480px;margin:0 auto;text-align:left'>
Arousal <span id=av></span><br><input id=a type=range min=-1 max=1 step=0.01 value=0.2 style='width:100%'><br>
Valence <span id=vv></span><br><input id=v type=range min=-1 max=1 step=0.01 value=0.1 style='width:100%'><br>
Power <span id=pv></span><br><input id=p type=range min=-1 max=1 step=0.01 value=0 style='width:100%'><br>
</div>
<pre id=m style='max-width:480px;margin:16px auto;text-align:left;color:#8f8'></pre>
<script src="/static/affect-servo.js"></script>
<script>
function go(){
  const a=+document.getElementById('a').value, v=+document.getElementById('v').value,
        p=+document.getElementById('p').value;
  document.getElementById('av').textContent=a.toFixed(2);
  document.getElementById('vv').textContent=v.toFixed(2);
  document.getElementById('pv').textContent=p.toFixed(2);
  document.getElementById('m').textContent =
    JSON.stringify(AffectServo.affectToDelivery(a,v,p), null, 1);
}
['a','v','p'].forEach(id=>document.getElementById(id).oninput=go); go();
</script></body></html>"""


@lab_bp.route("/party/lab/servo", methods=["GET"])
def lab_servo():
    return SERVO_RIG


PROP_OPS = {"uv_sphere", "cube", "cylinder", "torus", "cone", "plane"}
PROP_STYLES = {"matcap", "anime", "noir", "clay", "hero"}


@lab_bp.route("/party/prop/validate", methods=["POST"])
def prop_validate():
    """Validate a prop_job.v1 manifest (op vocab, materials, style).
    Pure logic, no Blender, no spend."""
    job = request.json or {}
    errors = []
    if job.get("version") != "prop_job.v1":
        errors.append("version must be prop_job.v1")
    prims = job.get("primitives")
    if not isinstance(prims, list) or not prims:
        errors.append("primitives: need a non-empty list")
    else:
        mats = job.get("materials") or {}
        for i, p in enumerate(prims):
            if not isinstance(p, dict):
                errors.append(f"primitives[{i}]: not an object")
                continue
            if p.get("op") not in PROP_OPS:
                errors.append(f"primitives[{i}].op {p.get('op')!r} not in {sorted(PROP_OPS)}")
            if p.get("material") not in mats:
                errors.append(f"primitives[{i}].material {p.get('material')!r} undefined")
    if job.get("style") not in PROP_STYLES:
        errors.append(f"style {job.get('style')!r} not in {sorted(PROP_STYLES)}")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400
    return jsonify({"ok": True, "ops": len(prims), "style": job["style"],
                    "note": "valid. Blender render is a GPU-box job (see docs/PROP-PIPELINE.md)."})
