"""Newsroom camera kit + director: the formal camera grammar of a news desk, as pure maths (no bpy), so it is
unit-tested without Blender (tests/contract/test_newsroom_cameras.py).

The newsroom version of the club kit (club_cameras.py): every shot is DERIVED from the studio's numbers (the
preset's Room Width / Ceiling Height / Wall size / Desk height) and the seated anchor's MEASURED eye and mouth
height, so swapping a 1.45 m VRoid for a 1.9 m GLB re-solves every frame.

Coordinates are the newsroom set's (newsroom_build.py): metres, Z up, floor z = 0, anchors seated at
(+-0.75, 0.55) facing -Y, the video wall a plane at y = Wall Y facing -Y.

Shots (cameras are VERTICAL-fit on a 20.25 mm sensor, so lens <-> frame height):

    CAM_CRANE_A   intro/outro crane top: high, wide and off-axis, looking down over the grid at the desk
    CAM_WIDE      establishing wide: the whole set, wall and desk, slightly off-centre
    CAM_TWO       two-shot of both seats (only when a co-anchor is cast)
    CAM_MEDIUM    waist-up single, straight-on (the anchor addresses this lens), eyes on the upper third
    CAM_CLOSE     head and shoulders, 3/4 from camera-right (~30 deg off the medium's axis: never a jump cut)
    CAM_XCU       extreme close-up for the punch: eyes and mouth, from the other side (~24 deg)
    CAM_DESK34    desk 3/4 from camera-left: the anchor, the desk's curve and the wall behind
    CAM_WALL      wall shot over the anchor's shoulder from camera-right: the WHOLE headline in frame
    CAM_SCREEN    the wall alone, near straight-on and high enough that the anchor's head stays out of frame
    CAM_PUSH_A/B  slow push-in, medium -> close on the same axis (the bake interpolates)
    CAM_DOLLY_A/B truck move: desk 3/4 sliding camera-right toward the axis while holding the anchor

The eye-line rule: every single (MEDIUM, CLOSE, XCU, PUSH_*, DOLLY_*, DESK34) is pitched so the eyes land on the
upper third (NDC y = +1/3 for MEDIUM/CLOSE/PUSH), solved exactly for a camera above or below the eye line.

The director (direct) turns a programme (lines with measured words, kinds open / tee / body / close, the intro and
outro) into cuts and moves with these rules, each one tested:

    grammar   intro -> crane down to the wide; first read -> medium; each story tee -> wall shot (the headline);
              story body -> medium, then close on an emphasis (a number, a marked *word*, an exclamation), desk
              3/4 / screen inserts / a slow push / a dolly across long reads; sign-off -> close, the last word ->
              pull out wide; outro -> crane up
    holds     no shot shorter than MIN_HOLD_MS, none longer than MAX_HOLD_MS while a read goes on (another angle is
              cut in at the next pause); never cut out of a move before it lands
    cuts      land between measured words (a pause, a comma, a sentence end), never mid-word
    no jumps  a cut between two shots must change size by >= 2 classes OR the camera's angle on the subject by
              >= 30 deg (the 30-degree rule); otherwise the director tries the next angle
    headline  the wall card shows its headline only when the whole wall rectangle is in frame (or none of it is);
              a partly framed wall (push-ins, close-ups, mid-move) shows the show's ambient art instead, so a
              headline is never cropped (wall_mode)
"""
import math

SENSOR_H = 20.25
ASPECT = 16 / 9
MIN_HOLD_MS = 2200
MAX_HOLD_MS = 8500
SEATS = {"anchor1": (0.75, 0.55), "anchor2": (-0.75, 0.55)}

# shot size classes (0 = tightest). Inserts (SCREEN) are a different subject: any cut to/from them is legal.
SIZE = {"CAM_XCU": 0, "CAM_CLOSE": 1, "CAM_PUSH_B": 1, "CAM_MEDIUM": 2, "CAM_PUSH_A": 2, "CAM_DESK34": 3,
        "CAM_DOLLY_A": 3, "CAM_DOLLY_B": 3, "CAM_TWO": 3, "CAM_WALL": 4, "CAM_WIDE": 5, "CAM_CRANE_A": 6}
INSERTS = {"CAM_SCREEN"}
ALIAS = {"CAM_PUSH_A": "CAM_MEDIUM"}     # PUSH_A is the medium's pose: a push from the medium is a continuation


def _alias(name):
    return ALIAS.get(name, name)


MOVES = {"crane_in": ("CAM_CRANE_A", "CAM_WIDE"), "crane_out": ("CAM_WIDE", "CAM_CRANE_A"),
         "push": ("CAM_PUSH_A", "CAM_PUSH_B"), "dolly": ("CAM_DOLLY_A", "CAM_DOLLY_B"),
         "pull_out": ("CAM_CLOSE", "CAM_WIDE")}


# ---- lens / projection --------------------------------------------------------------------------------------------
def lens_for_height(frame_h, dist):
    return SENSOR_H * dist / frame_h


def lens_for_width(frame_w, dist, aspect=ASPECT):
    return lens_for_height(frame_w / aspect, dist)


def _basis(pos, tgt):
    f = [tgt[i] - pos[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in f)) or 1.0
    f = [c / n for c in f]
    rn = math.hypot(f[1], f[0]) or 1.0
    r = [f[1] / rn, -f[0] / rn, 0.0]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return f, r, u


def project(pos, tgt, lens, pt, aspect=ASPECT):
    """NDC (x, y) of a world point for a camera at pos aimed at tgt (vertical fit, no roll); None behind it."""
    f, r, u = _basis(pos, tgt)
    d = [pt[i] - pos[i] for i in range(3)]
    z = sum(a * b for a, b in zip(d, f))
    if z <= 0.05:
        return None
    half_h = (SENSOR_H / 2) / lens
    return (sum(a * b for a, b in zip(d, r)) / z / (half_h * aspect), sum(a * b for a, b in zip(d, u)) / z / half_h)


def in_frame(pos, tgt, lens, pt, aspect=ASPECT, margin=1.0):
    p = project(pos, tgt, lens, pt, aspect)
    return p is not None and abs(p[0]) <= margin and abs(p[1]) <= margin


def lerp(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))


def smootherstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def ease_move(a, b, u, lead=1.5):
    """Pose between two shots at progress u: position smootherstep, aim leads the dolly (finishes at 1/lead),
    lens/focus/fstop smootherstep. a, b: shot dicts."""
    e, el = smootherstep(u), smootherstep(min(1.0, u * lead))
    return dict(pos=lerp(a["pos"], b["pos"], e), tgt=lerp(a["tgt"], b["tgt"], el), lens=a["lens"] + (b["lens"] - a["lens"]) * e,
                focus=lerp(a["focus"], b["focus"], e), fstop=a["fstop"] + (b["fstop"] - a["fstop"]) * e)


# ---- the studio --------------------------------------------------------------------------------------------------
def studio_numbers(inputs):
    """The numbers the kit needs from a newsroom preset's modifier inputs (defaults = the build's defaults)."""
    g = lambda k, d: float(inputs.get(k, d))
    return {"W": g("Room Width", 12.0), "D": g("Room Depth", 14.0), "H": g("Ceiling Height", 4.6),
            "by": g("Back Wall Y", 4.2), "wall_y": g("Wall Y", 2.7), "wall_w": g("Wall Width", 5.2),
            "wall_h": g("Wall Height", 2.6), "wall_z": g("Wall Centre Height", 2.05), "desk_h": g("Desk Height", 0.8),
            "desk_cy": g("Desk Centre Y", 1.75), "desk_r": g("Desk Radius", 2.0)}


def wall_corners(st, inset=0.0):
    hw, hh = st["wall_w"] / 2 - inset, st["wall_h"] / 2 - inset
    y = st["wall_y"] - 0.02
    return [(-hw, y, st["wall_z"] - hh), (hw, y, st["wall_z"] - hh), (hw, y, st["wall_z"] + hh), (-hw, y, st["wall_z"] + hh)]


def anchor_points(seat, eye, mouth=None, head_top=None):
    """Points on a seated anchor: head top (measured when known), eyes, mouth, shoulders, chest."""
    x, y = seat
    mouth = eye - 0.075 if mouth is None else mouth
    top = max(eye + 0.14, head_top or 0.0)
    return [(x, y, top), (x - 0.12, y, top - 0.05), (x + 0.12, y, top - 0.05), (x, y, eye), (x, y - 0.06, mouth), (x - 0.2, y, eye - 0.25), (x + 0.2, y, eye - 0.25),
            (x, y - 0.05, eye - 0.32)]


def framed(seat, eye, cam_xy, frame_h, top_frac, z_off=0.0, fstop=2.8):
    """A single on the anchor: camera at cam_xy, (eye + z_off) high, frame_h tall at the anchor, eyes top_frac down
    from the top edge (1/3 = upper third). Exact for a camera above or below the eye line."""
    sx, sy = seat
    px, py = cam_xy
    d = math.hypot(px - sx, py - sy)
    lens = lens_for_height(frame_h, d)
    cz = eye + z_off
    tan_half = (SENSOR_H / 2) / lens
    theta = math.atan2(eye - cz, d) - math.atan((1 - 2 * top_frac) * tan_half)
    aim_z = cz + d * math.tan(theta)
    head = (sx, sy, eye)
    return dict(pos=(px, py, cz), tgt=(sx, sy, aim_z), lens=lens, focus=head, fstop=fstop)


def fit_wall(pos, st, margin=0.9, aim=None):
    """Aim at the wall centre (or aim) and choose the longest lens that keeps all four corners within margin."""
    tgt = aim or (0.0, st["wall_y"], st["wall_z"])
    lens = 80.0
    while lens > 10.0 and not all(in_frame(pos, tgt, lens, c, ASPECT, margin) for c in wall_corners(st)):
        lens *= 0.97
    return tgt, lens


def shots(st, eye, mouth=None, seat="anchor1", coanchor=False, head_top=None):
    """Every shot as {name: dict(pos, tgt, lens, focus, fstop)} plus marks, from the studio numbers and the anchor's
    measured eye (and mouth) height."""
    sx, sy = SEATS[seat]
    side = 1.0 if sx >= 0 else -1.0
    head = (sx, sy, eye)
    H = st["H"]
    out = {}
    # WIDE: back far enough for the wall + flats; a little off-axis toward the anchor's side; above the desk line
    wy = -6.4
    wz = min(H - 0.5, 1.95)
    want_w = st["wall_w"] + 3.2
    dist = st["wall_y"] - wy
    lens = max(18.0, min(40.0, lens_for_width(want_w, dist)))
    out["CAM_WIDE"] = dict(pos=(0.45 * side, wy, wz), tgt=(0.15 * side, 1.2, 1.25 + 0.18 * (eye - 1.0)), lens=lens,
                           focus=head, fstop=5.6)
    # CRANE top: high (under the ceiling), further back and off to the anchor's other side, looking down
    cz = max(wz + 0.8, H - 0.35)
    out["CAM_CRANE_A"] = dict(pos=(-2.4 * side, -8.2, cz), tgt=(0.0, 1.6, 0.9), lens=max(16.0, lens * 0.82), focus=head, fstop=8.0)
    # singles on the measured eye line
    out["CAM_MEDIUM"] = framed(SEATS[seat], eye, (sx - 0.1 * side, sy - 3.15), 0.98, 1 / 3, z_off=-0.05, fstop=2.8)
    # close: 3/4 from camera-right, ~34 deg round from the medium axis (32 + the medium sits 1.8 deg the other way), so medium -> close is never a jump cut
    # (the anchor turns to it: gaze to camera on cuts)
    a = math.radians(32.0) * side
    out["CAM_CLOSE"] = framed(SEATS[seat], eye, (sx + 2.15 * math.sin(a), sy - 2.15 * math.cos(a)), 0.5, 1 / 3, z_off=-0.02, fstop=2.0)
    a = math.radians(-24.0) * side
    out["CAM_XCU"] = framed(SEATS[seat], eye, (sx + 1.55 * math.sin(a), sy - 1.55 * math.cos(a)), 0.27, 0.36, z_off=0.0, fstop=2.0)
    out["CAM_PUSH_A"] = dict(out["CAM_MEDIUM"])
    out["CAM_PUSH_B"] = framed(SEATS[seat], eye, (sx - 0.04 * side, sy - 2.35), 0.56, 1 / 3, z_off=-0.035, fstop=2.2)
    # desk 3/4 from the anchor's far side (camera-left for anchor1): desk curve + wall behind, eyes upper third
    out["CAM_DESK34"] = framed(SEATS[seat], eye, (sx - 2.55 * side, sy - 2.75), 1.75, 0.3, z_off=0.12, fstop=3.5)
    out["CAM_DOLLY_A"] = framed(SEATS[seat], eye, (sx - 2.9 * side, sy - 2.45), 1.6, 0.31, z_off=0.1, fstop=3.2)
    out["CAM_DOLLY_B"] = framed(SEATS[seat], eye, (sx - 1.15 * side, sy - 3.35), 1.25, 0.32, z_off=0.02, fstop=3.0)
    # wall shot over the anchor's shoulder from camera-right: whole headline in frame, anchor at the frame edge
    wp = (sx + 2.15 * side, -2.35, 1.6)
    aim = (-0.35 * side, st["wall_y"], st["wall_z"] - 0.12)
    tgt, lens = fit_wall(wp, st, 0.88, aim)
    out["CAM_WALL"] = dict(pos=wp, tgt=tgt, lens=lens, focus=(0.0, st["wall_y"], st["wall_z"]), fstop=4.0)
    # screen: the wall alone; walk candidates (further back, higher) until no anchor point is in frame
    ap = anchor_points(SEATS[seat], eye, mouth, head_top) + (anchor_points(SEATS["anchor2"], eye, mouth, head_top) if coanchor else [])
    best = None
    # (straight on first, then from the side away from the anchor so its head drops out of the frame's corner)
    for x in (0.0, -0.9 * side, -1.6 * side):
        for y in (-1.2, -1.6, -2.0, -2.5, -0.8):
            for z in (st["wall_z"] + 0.25, st["wall_z"] + 0.45, min(H - 0.3, st["wall_z"] + 0.7)):
                p = (x, y, z)
                t, ln = fit_wall(p, st, 0.94)
                if not any(in_frame(p, t, ln, q, ASPECT, 1.04) for q in ap):
                    best = dict(pos=p, tgt=t, lens=ln, focus=(0.0, st["wall_y"], st["wall_z"]), fstop=5.6)
                    break
            if best:
                break
        if best:
            break
    out["CAM_SCREEN"] = best or dict(pos=(0.0, -3.0, min(H - 0.3, st["wall_z"] + 0.7)), tgt=(0.0, st["wall_y"], st["wall_z"]),
                                     lens=24.0, focus=(0.0, st["wall_y"], st["wall_z"]), fstop=5.6)
    if coanchor:
        out["CAM_TWO"] = framed((0.0, sy), eye, (0.0, sy - 3.9), 1.25, 0.33, z_off=0.0, fstop=4.0)
        out["CAM_TWO"]["focus"] = (0.0, sy, eye)
    marks = {"MARK_EYE": head, "MARK_MOUTH": (sx, sy - 0.08, mouth if mouth is not None else eye - 0.075),
             "MARK_WALL": (0.0, st["wall_y"], st["wall_z"]), "MARK_DESK": (0.0, 0.0, st["desk_h"])}
    return out, marks


def azimuth(shot, subject):
    """Horizontal angle (deg) of the camera around the subject (0 = straight down -Y)."""
    dx, dy = shot["pos"][0] - subject[0], shot["pos"][1] - subject[1]
    return math.degrees(math.atan2(dx, -dy))


def legal_cut(a, b, kit, subject):
    """The 30-degree / size rule: a cut a -> b is legal if the size class changes by >= 2, or the angle on the subject
    changes by >= 30 deg, or either shot is an insert (a different subject)."""
    if a == b:
        return False
    if a in INSERTS or b in INSERTS:
        return True
    if abs(SIZE.get(a, 3) - SIZE.get(b, 3)) >= 2:
        return True
    return abs(azimuth(kit[a], subject) - azimuth(kit[b], subject)) >= 30.0


def wall_mode(pose, st, margin=1.0):
    """'headline' when the whole wall (all four corners) is in frame, or none of it is; 'ambient' when it is partly
    framed (a crop would cut the headline): the headline-crop fix for push-ins and close-ups."""
    c = [in_frame(pose["pos"], pose["tgt"], pose["lens"], p, ASPECT, margin) for p in wall_corners(st)]
    if all(c):
        return "headline"
    hw, hh = st["wall_w"] / 2, st["wall_h"] / 2
    grid = [(x * hw, st["wall_y"], st["wall_z"] + z * hh) for x in (-1, -0.5, 0, 0.5, 1) for z in (-1, 0, 1)]
    if not any(in_frame(pose["pos"], pose["tgt"], pose["lens"], p, ASPECT, margin) for p in grid):
        return "headline"
    return "ambient"


# ---- the director -----------------------------------------------------------------------------------------------------
def word_gaps(lines):
    """[(start_ms, end_ms)] between measured words and between lines (programme clock). Forced alignment often
    gives abutting words (no silence at all), so every word boundary is kept, as a zero-width gap: a cut there is
    still between two words."""
    gaps = []
    prev = 0
    for ln in lines:
        for w in ln.get("words", []):
            if w["start_ms"] >= prev:
                gaps.append((prev, w["start_ms"]))
            prev = max(prev, w["end_ms"])
    gaps.append((prev, prev + 10 ** 7))
    return gaps


def snap(t, gaps, window=700, min_gap=60):
    """Move a cut between words: into the nearest real pause (>= min_gap ms) within window ms, else onto the nearest
    word boundary (never left mid-word)."""
    for pass_min, win in ((min_gap, window), (0, None)):
        best, bd = None, None
        for a, b in gaps:
            if b - a < pass_min:
                continue
            if a <= t <= b and (b - a > 0 or t == a):
                return int(t)
            c = a + min(120, (b - a) / 2) if t < a else b - min(120, (b - a) / 2)
            d = abs(c - t)
            if (win is None or d <= win) and (bd is None or d < bd):
                best, bd = c, d
        if best is not None:
            return int(best)
    return int(t)


def is_emphasis(word):
    w = word.strip("\u201c\u201d\"'()[],.;:!?")
    return word.startswith("*") or any(ch.isdigit() for ch in w) or word.endswith("!")


def direct(prog, kit, subject, coanchor=False):
    """Cuts for a programme: [{t_ms, shot, move: (from, to, ms)|None, why}] in time order.

    prog: {"duration_ms", "intro_ms", "outro_ms", "lines": [{id, kind (open|tee|body|close), story, start_ms, end_ms,
           words: [{word, start_ms, end_ms}]}]} on the programme clock."""
    lines = prog["lines"]
    gaps = word_gaps(lines)
    cuts = []
    rot = ["CAM_DESK34", "CAM_SCREEN", "push", "CAM_CLOSE", "dolly", "CAM_MEDIUM"]
    state = {"alt": 0}

    def add(t, shot, why, move=None, force=False):
        """Append a cut (or a move starting at t). A move that starts from the shot already on air is a
        continuation, not a cut; everything else must respect the hold minimum and the 30-degree rule."""
        t = int(max(0, t))
        if cuts:
            last = cuts[-1]
            on_air = _alias(last["move"][1] if last.get("move") else last["shot"])
            first = _alias(move[0] if move else shot)
            if t <= last["t_ms"]:
                return False
            if last.get("move") and t < last["t_ms"] + last["move"][2] and not force:
                return False                                  # never cut out of a move before it lands
            continuation = move is not None and first == on_air
            if not continuation:
                if first == on_air:
                    return False
                if not force and t - last["t_ms"] < MIN_HOLD_MS:
                    return False
                if not legal_cut(on_air, first, kit, subject):
                    return False
            elif not force and t - last["t_ms"] < MIN_HOLD_MS:
                return False
        cuts.append({"t_ms": t, "shot": shot, "move": move, "why": why})
        return True

    def held(t):
        last = cuts[-1]
        return t - (last["t_ms"] + (last["move"][2] if last.get("move") else 0))

    def body_beats(ln):
        """Walk the read's word boundaries: punch in on an emphasis phrase, change the angle at a sentence end once
        a shot has had its say (~4.5 s), never let one shot run past MAX_HOLD_MS while the read goes on."""
        ws = ln.get("words", [])
        used = set()
        for k in range(1, len(ws)):
            g0, g1 = ws[k - 1]["end_ms"], ws[k]["start_ms"]
            sent = ws[k - 1]["word"].rstrip("\u201d\"')").endswith((".", "!", "?"))
            pause = g1 - g0 >= 90 or sent or ws[k - 1]["word"].endswith((",", ";", ":"))
            tc = int((g0 + g1) / 2)
            if ws[-1]["end_ms"] - tc < 1800:
                break                                  # don't cut in the read's last breath
            on = cuts[-1]["move"][1] if cuts[-1].get("move") else cuts[-1]["shot"]
            hit = next((j for j in range(k, min(len(ws), k + 4)) if j not in used and is_emphasis(ws[j]["word"])), None)
            if hit is not None and (pause or hit - k >= 2) and held(tc) >= MIN_HOLD_MS - 200:
                used.update(range(k, min(len(ws), k + 6)))
                if add(tc, "CAM_XCU" if on == "CAM_CLOSE" else "CAM_CLOSE", "emphasis: punch in"):
                    continue
            if not pause and held(tc) < MAX_HOLD_MS:
                continue
            if (sent and held(tc) >= 4500) or held(tc) >= MAX_HOLD_MS - 1500:
                for _ in range(len(rot)):
                    pick = rot[state["alt"] % len(rot)]
                    state["alt"] += 1
                    span = min(7000, max(3500, ws[-1]["end_ms"] - tc - 1500))
                    if pick in MOVES:
                        a_, b_ = MOVES[pick]
                        ok = add(tc, a_, f"long read: {pick}", move=(a_, b_, span))
                    else:
                        ok = add(tc, pick, "long read: change the angle" if sent else "max hold: change the angle")
                    if ok:
                        break

    intro = prog.get("intro_ms", 0)
    if intro > 0:
        add(0, "CAM_CRANE_A", "intro: crane down onto the set", move=("CAM_CRANE_A", "CAM_WIDE", max(2500, intro - 300)), force=True)
    else:
        add(0, "CAM_WIDE", "open wide", force=True)
    for i, ln in enumerate(lines):
        t0, t1 = ln["start_ms"], ln["end_ms"]
        kind = ln.get("kind", "body")
        if kind == "open":
            if i == 0 or lines[i - 1].get("kind") != "open":
                add(snap(t0 + 0.4 * (t1 - t0), gaps), "CAM_MEDIUM", "first read: settle on the medium")
        elif kind == "tee":
            add(snap(t0 - 250, gaps), "CAM_WALL", "story tee: the wall carries the headline")
        elif kind == "body":
            add(snap(t0 - 200, gaps), "CAM_MEDIUM", "story starts on the medium")
            body_beats(ln)
        elif kind == "close":
            if i == 0 or lines[i - 1].get("kind") != "close":
                add(snap(t0 - 200, gaps), "CAM_CLOSE", "sign-off: eye contact on the close")
            if i == len(lines) - 1 or lines[i + 1].get("kind") != "close":
                last_w = ln["words"][-1] if ln.get("words") else {"start_ms": t1 - 600}
                tp = snap(last_w["start_ms"] - 200, gaps)
                add(tp, "CAM_CLOSE", "the last word: pull out wide", move=("CAM_CLOSE", "CAM_WIDE", max(2600, t1 + 2200 - tp)), force=True)
    out_ms = prog.get("outro_ms", 0)
    if out_ms > 0 and lines:
        t = max(lines[-1]["end_ms"] + 2400, cuts[-1]["t_ms"] + (cuts[-1]["move"][2] if cuts[-1].get("move") else MIN_HOLD_MS))
        if t < prog["duration_ms"] - 1500:
            add(t, "CAM_WIDE", "outro: crane up and away", move=("CAM_WIDE", "CAM_CRANE_A", max(2500, prog["duration_ms"] - t)), force=True)
    return cuts


def pose_at(cuts, kit, t):
    """Camera pose at programme time t (ms) from the cuts (moves eased with the look leading the dolly)."""
    cur = cuts[0]
    for c in cuts:
        if c["t_ms"] <= t:
            cur = c
    if cur.get("move"):
        a, b, ms = cur["move"]
        u = (t - cur["t_ms"]) / max(1.0, ms)
        return ease_move(kit[a], kit[b], u), cur
    return dict(kit[cur["shot"]]), cur


def shot_name_at(cuts, t):
    """The shot on air at t (a move reports its start shot for the first half, its end shot after) and whether the
    camera is moving."""
    cur = cuts[0]
    for c in cuts:
        if c["t_ms"] <= t:
            cur = c
    if cur.get("move"):
        a, b, ms = cur["move"]
        moving = t - cur["t_ms"] < ms
        return (a if (t - cur["t_ms"]) < ms / 2 else b), moving
    return cur["shot"], False
