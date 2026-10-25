"""The newsroom cast: a character is one JSON file in sets/blender/news_cast/, so a presenter is one flag (--anchor <id>).

    python3 sets/blender/news_cast.py list                  # every cast member + its checkFace result
    python3 sets/blender/news_cast.py check vivi            # one member (exit 1 if its face fails)

A cast file (pure data, no code per character):

    id, name           the cast id (= file name) and the on-screen name (lower third)
    model              VRM/GLB path relative to the repo root (static/avatars/...)
    licence, source,   where the model came from and under which licence (CAST.md lists them all)
    author, credit
    voice              {"id": a PUBLIC Fish Audio voice, "name", "speed"}: TTS stays on s2.1-pro-free only
    face               per-rig expressive overrides on top of packages/stage-runtime/src/face/expressive-map.json:
                         "gains":  {channel: multiplier}      e.g. {"grin": 1.15} when a mesh's smile is shallow
                         "shapes": {channel: [[shape, w]...]} replace a channel's targets for this mesh only
                       (never hand-tune inside a bake: the map plus these overrides are the only face knobs)
    eye_line           metres added to the desk eye-line (DESK_EYE) for this character (taller/shorter sitters)
    wardrobe           {"match": [material-name substrings], "tint": "#RRGGBB", "amount": 0..1}: recolour the clothes
                       (a broadcast-safe mid-tone instead of a white top that clips under the key)
    light              {"emit": {material-key: share}} overrides of newsroom_anchor.ANCHOR_EMIT, {"albedo": {key: x}}
    rig                force a rig id from the map (optional; detection picks it otherwise)

resolve(arg) accepts a cast id, a cast JSON path, or a plain VRM/GLB path (then there is no cast entry: defaults).
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CAST_DIR = HERE / "news_cast"
DEFAULTS = {"face": {}, "eye_line": 0.0, "wardrobe": {}, "light": {}, "voice": {}, "rig": None}


def ids():
    return sorted(p.stem for p in CAST_DIR.glob("*.json"))


def load(cid):
    p = pathlib.Path(cid)
    if not (p.suffix == ".json" and p.exists()):
        p = CAST_DIR / f"{cid}.json"
    if not p.exists():
        raise SystemExit(f"no cast member {cid!r}: available {ids()}")
    c = dict(DEFAULTS, **json.loads(p.read_text()))
    c["id"] = c.get("id") or p.stem
    c["model_path"] = str((ROOT / c["model"]).resolve()) if not pathlib.Path(c["model"]).is_absolute() else c["model"]
    return c


def resolve(arg):
    """(model path, cast dict). A cast id or cast JSON -> its model; a model path -> a default entry; a model path
    that some cast file names -> that cast file (so an old --anchor static/avatars/x.vrm still gets its overrides)."""
    if not arg:
        arg = "house"
    p = pathlib.Path(arg)
    if p.suffix.lower() in (".vrm", ".glb", ".gltf"):
        full = (p if p.is_absolute() else (ROOT / p)).resolve() if not p.exists() else p.resolve()
        for cid in ids():
            c = load(cid)
            if pathlib.Path(c["model_path"]).resolve() == full:
                return c["model_path"], c
        c = dict(DEFAULTS, id=p.stem, name=p.stem, model=str(p), model_path=str(full))
        return str(full), c
    c = load(arg)
    return c["model_path"], c


def check(cid):
    import face_express as FX
    c = load(cid)
    names, nodes = FX.glb_names(c["model_path"])
    return c, FX.check_face(names, nodes)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    todo = ids() if cmd == "list" else sys.argv[2:]
    rc = 0
    for cid in todo:
        c, r = check(cid)
        print(json.dumps({"id": c["id"], "name": c.get("name"), "model": c["model"], "licence": c.get("licence"),
                          "voice": c.get("voice", {}).get("id"), "rig": r["rig"], "level": r["level"],
                          "missingCore": r["missingCore"], "warnings": r["warnings"]}))
        rc |= r["level"] == "fail"
    sys.exit(rc)
