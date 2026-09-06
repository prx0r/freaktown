#!/usr/bin/env python3
"""Motion Bank Pipeline — download, normalize, tag, and upload motion assets.

Fetches animation data from free sources (CMU Mocap, Mixamo),
normalizes them to canonical rigs, applies semantic tags,
and stores them in R2 + Postgres metadata.

Usage:
    python -m scripts.motion_pipeline --source cmu --upload
    python -m scripts.motion_pipeline --source mixamo --upload
    python -m scripts.motion_pipeline --seed-only
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import boto3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Configuration ───────────────────────────────────────────────────

R2_ENDPOINT = os.getenv("R2_S3_ENDPOINT", "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.getenv("R2_BUCKET", "freak-town")

MOTION_R2_PREFIX = "motions"
LOCAL_CACHE = Path("/tmp/killella-motions")


# ── R2 Client ───────────────────────────────────────────────────────

def get_r2_client():
    """Create an S3-compatible R2 client."""
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )


def upload_to_r2(local_path: str, r2_key: str) -> dict:
    """Upload a file to R2 and return metadata."""
    client = get_r2_client()
    file_size = os.path.getsize(local_path)
    sha256 = hashlib.sha256(open(local_path, "rb").read()).hexdigest()

    content_type = "application/octet-stream"
    if local_path.endswith(".glb"):
        content_type = "model/gltf-binary"
    elif local_path.endswith(".bvh"):
        content_type = "application/octet-stream"
    elif local_path.endswith(".json"):
        content_type = "application/json"

    client.upload_file(
        local_path,
        R2_BUCKET,
        r2_key,
        ExtraArgs={"ContentType": content_type},
    )

    return {
        "r2_key": r2_key,
        "file_size_bytes": file_size,
        "sha256": sha256,
        "url": f"https://{R2_BUCKET}.{R2_ENDPOINT.replace('https://', '')}/{r2_key}",
    }


# ── Motion Definition ───────────────────────────────────────────────

@dataclass
class MotionDef:
    """A motion to add to the bank."""
    name: str
    semantic: list[str]
    text: str
    style: list[str]
    body_class: str = "humanoid-v1"
    loop: bool = False
    root_motion: bool = False
    additive: bool = False
    bone_mask: str = "full"
    energy: float = 0.5
    amplitude: float = 0.5
    duration_ms: int = 0
    source: str = ""
    source_url: str = ""
    license: str = ""
    attribution: str = ""


# ── CMU Mocap Mappings ─────────────────────────────────────────────

# CMU mocap trial IDs that map well to semantic actions
CMU_MOTIONS = {
    # Walking / locomotion
    "01_01": MotionDef(
        name="cmu_walk_forward", semantic=["locomotion.walk", "locomotion.enter"],
        text="natural forward walk", style=["neutral", "casual"],
        loop=True, root_motion=True, energy=0.4, amplitude=0.3,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "01_02": MotionDef(
        name="cmu_walk_back", semantic=["locomotion.exit"],
        text="walking backward", style=["neutral"],
        loop=True, root_motion=True, energy=0.3, amplitude=0.2,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "05_01": MotionDef(
        name="cmu_creep", semantic=["locomotion.pace", "reaction.nervous"],
        text="cautious creeping pace", style=["nervous", "suspenseful"],
        root_motion=True, energy=0.3, amplitude=0.15,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "06_01": MotionDef(
        name="cmu_jog", semantic=["locomotion.walk"],
        text="light jogging", style=["energetic", "urgent"],
        loop=True, root_motion=True, energy=0.8, amplitude=0.5,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),

    # Gestures
    "09_01": MotionDef(
        name="cmu_hand_wave", semantic=["gesture.wave", "gesture.open_palm"],
        text="hand waving gesture", style=["friendly", "enthusiastic"],
        additive=True, bone_mask="upper_body", energy=0.5, amplitude=0.6,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "10_01": MotionDef(
        name="cmu_point", semantic=["gesture.point", "gesture.emphasize"],
        text="pointing gesture", style=["direct", "assertive"],
        additive=True, bone_mask="upper_body", energy=0.5, amplitude=0.5,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "12_01": MotionDef(
        name="cmu_arm_cross", semantic=["pose.cross_arms", "reaction.bored"],
        text="crossing arms, waiting", style=["bored", "impatient"],
        additive=True, bone_mask="upper_body", energy=0.2, amplitude=0.3,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "14_01": MotionDef(
        name="cmu_shrug", semantic=["gesture.shrug", "reaction.confused"],
        text="shoulder shrug gesture", style=["uncertain", "dismissive"],
        additive=True, bone_mask="upper_body", energy=0.3, amplitude=0.4,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),

    # Reactions
    "17_01": MotionDef(
        name="cmu_sit_down", semantic=["pose.slump", "reaction.bored"],
        text="sitting down, slumping", style=["defeated", "tired"],
        bone_mask="full", energy=0.1, amplitude=0.2,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "18_01": MotionDef(
        name="cmu_stand_up", semantic=["pose.confident", "locomotion.enter"],
        text="standing up from chair", style=["confident", "alert"],
        bone_mask="full", energy=0.4, amplitude=0.3,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "35_01": MotionDef(
        name="cmu_clap", semantic=["reaction.enjoy_laugh", "gesture.emphasize"],
        text="clapping hands", style=["appreciative", "enthusiastic"],
        additive=True, bone_mask="upper_body", energy=0.6, amplitude=0.6,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "39_01": MotionDef(
        name="cmu_frustrated", semantic=["reaction.annoyed", "reaction.nervous"],
        text="frustrated gesture, hands up", style=["frustrated", "exasperated"],
        additive=True, bone_mask="upper_body", energy=0.6, amplitude=0.5,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),

    # Idles
    "40_01": MotionDef(
        name="cmu_idle_shift", semantic=["procedural.sway", "procedural.micro_fidget"],
        text="shifting weight while standing", style=["restless", "impatient"],
        loop=True, additive=True, bone_mask="full", energy=0.15, amplitude=0.08,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
    "41_01": MotionDef(
        name="cmu_idle_still", semantic=["procedural.breathing"],
        text="standing still with natural breathing", style=["calm", "neutral"],
        loop=True, bone_mask="full", energy=0.05, amplitude=0.03,
        source="cmu", license="no-restrictions",
        attribution="CMU Graphics Lab Motion Capture Database",
    ),
}


# ── Pipeline Steps ──────────────────────────────────────────────────

def download_cmu_trial(trial_id: str, output_dir: Path) -> Path | None:
    """Download a CMU mocap BVH file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"cmu_{trial_id}.bvh"

    if output_file.exists():
        print(f"  [cache] {output_file}")
        return output_file

    # CMU mocap data is available via their FTP
    # For now, create a placeholder - in production we'd download real data
    print(f"  [placeholder] CMU trial {trial_id} - would download from CMU FTP")
    return None


def create_placeholder_glb(motion_def: MotionDef, output_dir: Path) -> Path:
    """Create a placeholder GLB for a motion (real pipeline would convert BVH→GLB).

    In production, this would:
    1. Load the BVH file
    2. Retarget to killella-humanoid-v1 canonical rig
    3. Optimize with glTF Transform + Meshopt
    4. Export as GLB
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    placeholder = output_dir / f"{motion_def.name}.json"

    # Store the motion metadata as a placeholder
    metadata = {
        "name": motion_def.name,
        "semantic": motion_def.semantic,
        "text": motion_def.text,
        "style": motion_def.style,
        "body_class": motion_def.body_class,
        "loop": motion_def.loop,
        "root_motion": motion_def.root_motion,
        "additive": motion_def.additive,
        "bone_mask": motion_def.bone_mask,
        "energy": motion_def.energy,
        "amplitude": motion_def.amplitude,
        "source": motion_def.source,
        "license": motion_def.license,
        "attribution": motion_def.attribution,
        "note": "placeholder - real pipeline would produce .glb",
    }

    with open(placeholder, "w") as f:
        json.dump(metadata, f, indent=2)

    return placeholder


def process_motion(motion_def: MotionDef, cache_dir: Path, upload: bool) -> dict:
    """Process a single motion: download, normalize, tag, optionally upload."""
    print(f"\n[{motion_def.name}]")
    print(f"  semantic: {motion_def.semantic}")
    print(f"  text: {motion_def.text}")

    # 1. Download source
    local_path = None
    if motion_def.source == "cmu" and motion_def.source_url:
        local_path = download_cmu_trial(motion_def.source_url, cache_dir)

    # 2. Create placeholder (or use downloaded file)
    if local_path is None:
        local_path = create_placeholder_glb(motion_def, cache_dir)

    # 3. Upload to R2
    r2_info = {}
    if upload and local_path:
        r2_key = f"{MOTION_R2_PREFIX}/{motion_def.body_class}/{motion_def.name}.json"
        try:
            r2_info = upload_to_r2(str(local_path), r2_key)
            print(f"  uploaded: {r2_info['r2_key']}")
        except Exception as e:
            print(f"  upload failed: {e}")

    # 4. Return metadata for DB insertion
    asset_id = str(uuid.uuid4())
    return {
        "id": asset_id,
        "name": motion_def.name,
        "semantic": motion_def.semantic,
        "text": motion_def.text,
        "style": motion_def.style,
        "body_class": motion_def.body_class,
        "loop": motion_def.loop,
        "root_motion": motion_def.root_motion,
        "additive": motion_def.additive,
        "bone_mask": motion_def.bone_mask,
        "energy": motion_def.energy,
        "amplitude": motion_def.amplitude,
        "source": motion_def.source,
        "license": motion_def.license,
        "attribution": motion_def.attribution,
        "r2_key": r2_info.get("r2_key", ""),
        "file_size_bytes": r2_info.get("file_size_bytes", 0),
    }


def run_pipeline(sources: list[str], upload: bool = False):
    """Run the full motion bank pipeline."""
    cache_dir = LOCAL_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)

    all_assets = []

    # Process CMU motions
    if "cmu" in sources:
        print("\n=== CMU Mocap Pipeline ===")
        print(f"Processing {len(CMU_MOTIONS)} motions...")

        for trial_id, motion_def in CMU_MOTIONS.items():
            motion_def.source_url = trial_id
            asset = process_motion(motion_def, cache_dir / "cmu", upload)
            all_assets.append(asset)

    # Process seed motions (already defined in code)
    if "seed" in sources:
        print("\n=== Seed Motions ===")
        from backend.models.motion_assets import SEED_MOTIONS
        print(f"Processing {len(SEED_MOTIONS)} seed motions...")

        for motion in SEED_MOTIONS:
            asset = {
                "id": motion.id,
                "name": motion.name,
                "semantic": motion.semantic,
                "text": motion.text,
                "style": motion.style,
                "body_class": motion.body_class,
                "loop": motion.loop,
                "root_motion": motion.root_motion,
                "additive": motion.additive,
                "bone_mask": motion.bone_mask,
                "energy": motion.energy,
                "amplitude": motion.amplitude,
                "source": motion.source,
                "license": motion.license,
                "attribution": motion.attribution,
                "r2_key": "",
                "file_size_bytes": 0,
            }
            all_assets.append(asset)
            print(f"  [{motion.name}] {motion.semantic}")

    # Write manifest
    manifest_path = cache_dir / "motion_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(all_assets, f, indent=2)

    print(f"\n=== Done ===")
    print(f"Total motions: {len(all_assets)}")
    print(f"Manifest: {manifest_path}")

    return all_assets


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Killella Motion Bank Pipeline")
    parser.add_argument("--source", nargs="+", default=["cmu", "seed"],
                       choices=["cmu", "mixamo", "seed"],
                       help="Motion sources to process")
    parser.add_argument("--upload", action="store_true",
                       help="Upload processed motions to R2")
    parser.add_argument("--seed-only", action="store_true",
                       help="Only process seed motions (no download)")
    args = parser.parse_args()

    sources = ["seed"] if args.seed_only else args.source
    assets = run_pipeline(sources, upload=args.upload)

    # Print summary
    print("\n=== Asset Summary ===")
    by_source = {}
    for a in assets:
        src = a["source"]
        by_source.setdefault(src, []).append(a)

    for src, items in by_source.items():
        print(f"  {src}: {len(items)} motions")

    by_body = {}
    for a in assets:
        bc = a["body_class"]
        by_body.setdefault(bc, []).append(a)

    for bc, items in by_body.items():
        print(f"  {bc}: {len(items)} motions")


if __name__ == "__main__":
    main()
