#!/usr/bin/env bash
# Install Blender 5.2.2 (official linux-x64 build, SHA-256 checked) and video-to-blender at a pinned commit.
# Used by .github/workflows/blender-sets.yml; works on any x86-64 Debian/Ubuntu box.
set -euo pipefail
BLENDER_VERSION="${BLENDER_VERSION:-5.2.2}"
BLENDER_SERIES="${BLENDER_VERSION%.*}"
BLENDER_SHA256="${BLENDER_SHA256:-84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168}"
V2B_COMMIT="${V2B_COMMIT:-bfeca3ff77d1468f3f9c6a801342cb6286e3f6b1}"
DEST="${BLENDER_HOME:-$HOME/blender}"
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 \
    libgl1 libegl1 libgl1-mesa-dri ffmpeg >/dev/null
fi
name="blender-${BLENDER_VERSION}-linux-x64"
if [ ! -x "$DEST/$name/blender" ]; then
  curl -fsSL -o "/tmp/$name.tar.xz" "https://download.blender.org/release/Blender${BLENDER_SERIES}/$name.tar.xz"
  echo "${BLENDER_SHA256}  /tmp/$name.tar.xz" | sha256sum -c -
  mkdir -p "$DEST" && tar -xJf "/tmp/$name.tar.xz" -C "$DEST"
fi
"$DEST/$name/blender" -b --version | head -1
if [ ! -d "${V2B_DIR:-$HOME/video-to-blender}/.git" ]; then
  git clone -q https://github.com/gokayfem/video-to-blender.git "${V2B_DIR:-$HOME/video-to-blender}"
fi
git -C "${V2B_DIR:-$HOME/video-to-blender}" checkout -q "$V2B_COMMIT"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "BLENDER=$DEST/$name/blender" >> "$GITHUB_ENV"
  echo "V2B_SKILL=${V2B_DIR:-$HOME/video-to-blender}/skills/procedural-blender-nodes" >> "$GITHUB_ENV"
fi
