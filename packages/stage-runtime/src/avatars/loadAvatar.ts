/**
 * Avatar resolution in doctrine order: VRM → GLB (sniffed) → BASIC.
 * Any load failure falls through to BASIC: the stage always has a performer.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils, type VRM } from '@pixiv/three-vrm';
import type { AvatarDriver } from './types';
import { VrmAvatar } from './VrmAvatar';
import { GlbAvatar } from './GlbAvatar';
import { BasicAvatar, type BasicAvatarOptions } from './BasicAvatar';
import { normalizeHeight } from './normalize';
import { CpuDeformer } from './CpuDeformer';

export interface AvatarSpec {
  /** URL of a .vrm/.glb, or "basic" / "basic:robot". Empty → BASIC. */
  url?: string;
  name?: string;
  seed?: string;
  height?: number;
  /** Swap MToon for MeshStandard + drop outlines (software GL / weak GPUs). */
  lite?: boolean;
  /** Deform skinned/morphed meshes on the CPU (no vertex texture fetch). */
  cpuSkinning?: boolean;
}

/** MToon → MeshStandardMaterial (same textures), outline passes hidden. */
function liteMaterials(root: THREE.Object3D): void {
  const hidden = new THREE.MeshBasicMaterial({ visible: false });
  const conv = new Map<THREE.Material, THREE.Material>();
  const swap = (m: THREE.Material): THREE.Material => {
    const anyM = m as THREE.Material & { isOutline?: boolean; map?: THREE.Texture | null; color?: THREE.Color; isShaderMaterial?: boolean };
    if (anyM.isOutline) return hidden;
    if (!anyM.isShaderMaterial) return m;
    let out = conv.get(m);
    if (!out) {
      out = new THREE.MeshStandardMaterial({
        map: anyM.map ?? null,
        color: anyM.color ? anyM.color.clone() : new THREE.Color(0xffffff),
        transparent: m.transparent, alphaTest: m.alphaTest, side: m.side,
        roughness: 0.85, metalness: 0,
        depthWrite: m.depthWrite,
      });
      conv.set(m, out);
    }
    return out;
  };
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(swap) : swap(mesh.material);
  });
}

export interface LoadedAvatar {
  driver: AvatarDriver;
  /** Set when the requested body failed and BASIC stood in. */
  fallbackReason?: string;
}

function basic(spec: AvatarSpec, variant: BasicAvatarOptions['variant']): AvatarDriver {
  const d = new BasicAvatar({ name: spec.name ?? 'BASIC', seed: spec.seed, variant });
  normalizeHeight(d.root, spec.height ?? 1.7);
  return d;
}

export async function loadAvatar(spec: AvatarSpec): Promise<LoadedAvatar> {
  const url = (spec.url ?? '').trim();
  if (!url || url === 'basic' || url.startsWith('basic:')) {
    return { driver: basic(spec, url === 'basic:robot' ? 'robot' : 'human') };
  }
  try {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    const gltf = await loader.loadAsync(url);
    const vrm = gltf.userData.vrm as VRM | undefined;
    let driver: AvatarDriver;
    if (vrm) {
      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.rotateVRM0(vrm); // VRM0 faces -Z; VRM1 already faces +Z
      vrm.scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.isMesh) { m.castShadow = true; m.frustumCulled = false; }
      });
      if (spec.lite) liteMaterials(vrm.scene);
      driver = new VrmAvatar(vrm, spec.name ?? ((vrm.meta as { name?: string; title?: string } | undefined)?.name ?? (vrm.meta as { title?: string } | undefined)?.title ?? 'VRM'));
    } else {
      driver = new GlbAvatar(gltf.scene, gltf.animations ?? [], spec.name ?? 'GLB');
    }
    normalizeHeight(driver.root, spec.height ?? 1.7);
    if (spec.cpuSkinning) {
      const deformer = new CpuDeformer(driver.root);
      const update = driver.update.bind(driver);
      driver.update = (dt: number) => { update(dt); deformer.update(); };
    }
    return { driver };
  } catch (e) {
    const reason = e instanceof Error ? e.message : String(e);
    return { driver: basic(spec, 'human'), fallbackReason: `avatar load failed (${reason}); BASIC stands in` };
  }
}
