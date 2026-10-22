"""Club camera kit: one set of named cameras and marks that every club preset and every show uses, plus the shot
grammar that picks a shot from a performance timeline.

Coordinates are the club set's (club_build.py): metres, Z up, stage top z = 0, the comic stands at the origin facing
-Y (the house), the back wall at y = Back Wall Y. Every shot is derived from the room numbers (Room Width/Depth,
Riser Height, Stage Width/Depth, Theatre Rows, Rake, Row Pitch) and the comic's MEASURED eye height, so a 1.45 m
VRoid and a 1.75 m GLB both get the eye-line on the upper third.

    CAM_WIDE       establishing: from the house, above the heads (raked rows: above that row's heads), lens chosen so
                   the stage width fills ~85% of the frame; never closer than the front row + 1 m
    CAM_MEDIUM     waist-up, a touch camera-left of centre (clears the mic stand), eye-line on the upper third
    CAM_CLOSE      head and shoulders, 3/4 from camera-right so the mic (below and in front of the mouth) never covers
                   the lips; shallow depth of field on the eyes
    CAM_XCU        extreme close-up for the punch: eyes and mouth, f/2
    CAM_OTS        over-the-shoulder crowd reverse: behind the comic's right shoulder, looking out at the house
    CAM_PUSH_A/B   the two ends of the slow push-in (medium -> close); the bake interpolates between them
    CAM_CROWD      crowd cutaway from the stage-left lip, low, across the front tables / rows
    MARK_EYE, MARK_MOUTH, MARK_CROWD, MARK_LIP   empties the shots aim at (also handy for the web stage)

The shot grammar (pick_shots) reads the club-clip timeline (club_clip.py) and returns cuts:
    open WIDE on the first line, then MEDIUM          establish, then settle
    push in (PUSH_A -> PUSH_B) across a bit's setups  build
    the look before a punch -> CLOSE                  the beat and the look
    the punch word -> XCU (short punch) / hold CLOSE  the hit
    a big laugh -> OTS crowd reverse, then CROWD on the next big one; tag laughs stay on the comic (reaction)
    act-outs -> MEDIUM (the body sells it)
    last laugh -> WIDE pull-out
    never a shot shorter than MIN_SHOT_MS, never a cut to the same shot
"""
import math

MIN_SHOT_MS = 1400

# 36 mm sensor width, 16:9 frame: vertical sensor 20.25 mm (cameras are VERTICAL-fit so lens <-> frame height)
SENSOR_H = 20.25


def lens_for_height(frame_h, dist):
    """Lens (mm, vertical fit on SENSOR_H) that makes a subject frame_h metres tall fill the frame at dist."""
    return SENSOR_H * dist / frame_h


def lens_for_width(frame_w, dist, aspect=16 / 9):
    return lens_for_height(frame_w / aspect, dist)


def _floor_z(room, y):
    """House floor (or that row's floor in a raked house) at depth y (y < front of stage)."""
    R = room["Riser Height"]
    if not room.get("Theatre Rows"):
        return -R
    front = room["Back Wall Y"] - room["Stage Depth"]
    first = front - 1.6
    k = max(0.0, (first - y) / room.get("Row Pitch", 0.95))
    return -R + math.floor(k + 0.5) * room.get("Rake", 0.18)


def shots(room, eye, aspect=16 / 9, crowd=None):
    """Every shot as {name: dict(pos, tgt, lens, focus, fstop)} from the room numbers and the comic's eye height.
    crowd: optional (x, y, z) centroid of the seated people near the stage (measured from the built set), so the crowd
    cutaway finds a sparse open-mic house instead of an empty corner."""
    W, D, wy = room["Room Width"], room["Room Depth"], room["Back Wall Y"]
    R, SW, SD = room["Riser Height"], room["Stage Width"], room["Stage Depth"]
    H = room["Ceiling Height"]
    front = wy - SD                       # stage lip
    back = wy - D                         # rear wall
    mouth = eye - 0.075
    head = (0.0, 0.0, eye)
    out = {}

    # WIDE: as deep as the room allows (rear wall - 0.8 m), but no deeper than needed for the stage to fill 85% of
    # the frame with a 28-50 mm lens; above the heads at that depth
    want_w = min(SW * 1.18, 8.5)          # a 12 m theatre stage would make the comic a speck
    y = max(back + 0.8, front - 9.5)
    dist = front - y                       # fit the stage LIP (nearest, widest in frame), not the comic
    lens = max(18.0, min(50.0, lens_for_width(want_w, dist, aspect)))
    z = min(H - 0.5, _floor_z(room, y) + 1.25 + 0.75)
    tgt = (0.0, front * 0.4, 0.55 + 0.25 * eye + 0.02 * dist)     # between the lip and the head top
    out["CAM_WIDE"] = dict(pos=(0.35, y, z), tgt=tgt, lens=lens, focus=head, fstop=5.6)

    def framed(pos_xy, frame_h, top_frac, z_off=0.0, fstop=2.8, aim_x=0.0):
        """A shot at pos_xy (x, y) at eye height + z_off whose frame is frame_h tall at the comic, with the eyes
        top_frac down from the top edge (1/3 = upper third)."""
        px, py = pos_xy
        d = math.hypot(px, py)
        lens = lens_for_height(frame_h, d)
        cz = eye + z_off
        # pitch the camera so the eyes land top_frac down the frame (NDC y = 1 - 2 top_frac), exact for a camera
        # above or below the eye line: theta = elevation(eye) - atan(ndc * tan(vfov/2))
        tan_half = (SENSOR_H / 2) / lens
        theta = math.atan2(eye - cz, d) - math.atan((1 - 2 * top_frac) * tan_half)
        aim_z = cz + d * math.tan(theta)
        return dict(pos=(px, py, cz), tgt=(aim_x, 0.0, aim_z), lens=lens, focus=head, fstop=fstop)

    out["CAM_MEDIUM"] = framed((-0.45, -3.4), 1.05, 1 / 3, z_off=-0.12, fstop=2.8)
    out["CAM_CLOSE"] = framed((0.62, -2.15), 0.48, 0.33, z_off=-0.02, fstop=2.0)
    out["CAM_XCU"] = framed((0.3, -1.6), 0.27, 0.36, z_off=0.0, fstop=2.0)
    out["CAM_PUSH_A"] = dict(out["CAM_MEDIUM"])
    out["CAM_PUSH_B"] = framed((0.15, -2.4), 0.58, 0.32, z_off=-0.04, fstop=2.2)
    # OTS: behind the comic's right shoulder (comic faces -Y, their right is -X), looking out over the house
    house_mid = (0.6, (front + max(back, front - 9.0)) / 2, _floor_z(room, front - 3.0) + 0.9)
    out["CAM_OTS"] = dict(pos=(-0.5, 0.95, eye + 0.12), tgt=house_mid, lens=30.0,
                          focus=(0.0, front - 3.0, house_mid[2]), fstop=4.0)
    # crowd cutaway: low from the stage-left lip, across the front of the house
    lip_x = min(SW / 2 - 0.4, 2.6)
    cz = _floor_z(room, front - 2.5) + 1.1
    reach = min(4.0, max(2.5, (front - back) * 0.4))
    # cafe houses keep a clear centre aisle (|x| < ~1.45 m): look across into the tables, not down the aisle
    ax = -1.0 if room.get("Theatre Rows") else -min(W / 2 - 1.0, 2.4)
    tgt = (ax, front - reach, cz - 0.35)
    side = 1.0
    if crowd is not None:
        tgt = (crowd[0], crowd[1], crowd[2])
        side = -1.0 if crowd[0] > 0 else 1.0          # shoot across the house from the other side of the lip
    pos = (side * lip_x, front + 0.25, max(cz, 0.6))
    dist = math.dist(pos, tgt)
    out["CAM_CROWD"] = dict(pos=pos, tgt=tgt, lens=20.0, focus=tuple(pos[i] + (tgt[i] - pos[i]) * 0.8 for i in range(3)),
                            fstop=2.8 if dist > 2 else 4.0)
    marks = {"MARK_EYE": head, "MARK_MOUTH": (0.0, -0.08, mouth), "MARK_CROWD": house_mid,
             "MARK_LIP": (0.0, front, 0.0)}
    return out, marks


def build(bpy, sc, room, eye, aspect=16 / 9, crowd=None):
    """Create the named cameras and marks in the scene. Returns {name: camera object}."""
    from mathutils import Vector
    spec, marks = shots(room, eye, aspect, crowd)
    cams = {}
    for name, s in spec.items():
        cd = bpy.data.cameras.new(name)
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = SENSOR_H
        cd.lens = s["lens"]
        cd.clip_start, cd.clip_end = 0.05, 200.0
        ob = bpy.data.objects.new(name, cd)
        ob.location = s["pos"]
        # location/rotation, never matrix_world, on objects made this run (black frames otherwise)
        ob.rotation_euler = (Vector(s["tgt"]) - Vector(s["pos"])).to_track_quat("-Z", "Y").to_euler()
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(s["focus"]) - Vector(s["pos"])).length
        cd.dof.aperture_fstop = s["fstop"]
        sc.collection.objects.link(ob)
        ob["club_shot"] = {"tgt": list(s["tgt"]), "focus": list(s["focus"])}
        cams[name] = ob
    for name, p in marks.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "SPHERE", 0.05
        e.location = p
        sc.collection.objects.link(e)
    return cams, spec


# ---- shot grammar --------------------------------------------------------------------------------------------------
def pick_shots(tl):
    """Cuts for a club-clip timeline: [{t_ms, shot, push: (from, to, ms)|None, why}] in time order."""
    lines, laughs, looks = tl["lines"], tl["laughs"], tl.get("looks", [])
    look_by = {lk["line"]: lk for lk in looks}
    laugh_by = {lg["after"]: lg for lg in laughs}
    cuts = []

    def cut(t, shot, why, push=None):
        t = int(t)
        if cuts and cuts[-1]["shot"] == shot and not push:
            return
        if cuts and t - cuts[-1]["t_ms"] < MIN_SHOT_MS:
            if cuts[-1]["why"].startswith(("punch", "look")) and not why.startswith(("punch", "look")):
                return           # keep the punch / look shot; drop the weaker cut
            cuts[-1].update(shot=shot, why=why, push=push)      # replace the weaker cut
            return
        cuts.append({"t_ms": t, "shot": shot, "why": why, "push": push})

    cut(0, "CAM_WIDE", "open: establish the room")
    big = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln["id"] in look_by and (i == 0 or lines[i - 1]["id"] not in look_by):
            cut(look_by[ln["id"]]["t_ms"], "CAM_CLOSE", "look: the beat before the punch")
        if i == 0 and ln["id"] not in look_by:
            cut(ln["t_ms"] + ln["dur_ms"] * 0.55, "CAM_MEDIUM", "settle after the opener")
        elif ln["role"] == "setup":
            # a run of setups is the build: push in across it
            j = i
            while j + 1 < len(lines) and lines[j + 1]["role"] == "setup":
                j += 1
            t0, t1 = ln["t_ms"], lines[j]["t_ms"] + lines[j]["dur_ms"]
            cut(t0 - 150, "CAM_PUSH_A", "build: push in across the setups", push=("CAM_PUSH_A", "CAM_PUSH_B", max(2500, t1 - t0)))
            i = j
            ln = lines[i]
        elif ln["role"] == "act-out":
            cut(ln["t_ms"] - 200, "CAM_MEDIUM", "act-out: the body sells it")
        elif ln["role"] == "tag":
            cut(ln["t_ms"] - 120, "CAM_MEDIUM" if (i % 2) else "CAM_CLOSE", "tag")
        if ln["id"] in look_by:
            pass
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt is not None and nxt["id"] in look_by:
            lk = look_by[nxt["id"]]
            cut(lk["t_ms"], "CAM_CLOSE", "look: the beat before the punch")
        if ln["role"] in ("punch", "callback", "closer"):
            if ln["id"] in look_by:
                pass
            if ln.get("hit_ms"):
                lead = 650 if ln["dur_ms"] < 2600 else 1100
                tx = max(ln["t_ms"] + 200, ln["hit_ms"] - lead, (cuts[-1]["t_ms"] + MIN_SHOT_MS) if cuts else 0)
                if tx <= ln["hit_ms"]:      # in on the hit; if the look shot is still young, the look carries it
                    cut(tx, "CAM_XCU", "punch: extreme close-up on the hit")
        lg = laugh_by.get(ln["id"])
        if lg:
            last = lg is laughs[-1] and ln["role"] in ("closer", "tag", "callback")
            if last:
                cut(lg["t_ms"] + 250, "CAM_WIDE", "last laugh: pull out wide")
            elif lg["size"] >= 0.9:
                big += 1
                shot = "CAM_OTS" if big % 2 else "CAM_CROWD"
                cut(lg["t_ms"] + 120, shot, "laugh: crowd reverse")
                # reaction: back on the comic for the smirk before the next line
                cut(max(lg["t_ms"] + lg["dur_ms"] * 0.62, lg["t_ms"] + 120 + MIN_SHOT_MS), "CAM_CLOSE", "reaction after the laugh")
            else:
                pass     # tag laughs stay on the comic: the reaction is the shot
        i += 1
    return cuts
