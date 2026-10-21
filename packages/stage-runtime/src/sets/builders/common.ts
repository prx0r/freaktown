/** Shared procedural helpers for set builders (canvas textures, primitives, lights). */
import * as THREE from 'three';
import type { LightingRig, SetDefinition } from '../types';

export interface BuildContext { shadows: boolean; low: boolean }

export interface BuiltSet {
  group: THREE.Group;
  update(dt: number, wallMs: number): void;
  setHeadline?(text: string, kicker?: string): void;
  setOnAir?(on: boolean): void;
  dispose(): void;
}

export function canvasTexture(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d')!);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export function redraw(tex: THREE.CanvasTexture, draw: (ctx: CanvasRenderingContext2D) => void): void {
  const c = tex.image as HTMLCanvasElement;
  draw(c.getContext('2d')!);
  tex.needsUpdate = true;
}

export const std = (color: number | string, rough = 0.6, metal = 0.05, emissive?: number | string, ei = 1) =>
  new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, ...(emissive !== undefined ? { emissive, emissiveIntensity: ei } : {}) });
export const glow = (color: number | string) => new THREE.MeshBasicMaterial({ color, toneMapped: false });

export function box(w: number, h: number, d: number, m: THREE.Material, x = 0, y = 0, z = 0, shadow = false): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
  mesh.position.set(x, y, z);
  mesh.castShadow = shadow; mesh.receiveShadow = true;
  return mesh;
}
export function cyl(rt: number, rb: number, h: number, m: THREE.Material, x = 0, y = 0, z = 0, seg = 24): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), m);
  mesh.position.set(x, y, z);
  mesh.receiveShadow = true;
  return mesh;
}

export function applyLighting(group: THREE.Group, rig: LightingRig, ctx: BuildContext): void {
  group.add(new THREE.AmbientLight(rig.ambient.color, rig.ambient.intensity));
  group.add(new THREE.HemisphereLight(0xffffff, 0x202020, 0.35));
  const key = new THREE.DirectionalLight(rig.key.color, rig.key.intensity);
  key.position.set(...rig.key.position);
  key.castShadow = ctx.shadows;
  if (ctx.shadows) { key.shadow.mapSize.set(1024, 1024); key.shadow.camera.left = -5; key.shadow.camera.right = 5; key.shadow.camera.top = 5; key.shadow.camera.bottom = -5; }
  group.add(key);
  for (const l of [rig.fill, rig.rim]) {
    if (!l) continue;
    const d = new THREE.DirectionalLight(l.color, l.intensity);
    d.position.set(...l.position);
    group.add(d);
  }
}

/** A simple chair facing +Z at the origin (seat top 0.48 m). */
export function chair(m: THREE.Material, back = true): THREE.Group {
  const g = new THREE.Group();
  g.add(box(0.48, 0.07, 0.46, m, 0, 0.45, 0, true));
  if (back) g.add(box(0.48, 0.6, 0.06, m, 0, 0.78, -0.22, true));
  g.add(cyl(0.03, 0.03, 0.42, std(0x222222, 0.4, 0.7), 0, 0.21, 0, 8));
  g.add(cyl(0.22, 0.22, 0.03, std(0x222222, 0.4, 0.7), 0, 0.015, 0, 16));
  return g;
}

export function placeAtSeats(def: SetDefinition, make: () => THREE.Object3D, group: THREE.Group, back = 0): void {
  for (const s of def.seats) {
    const o = make();
    o.position.set(s.position[0] - Math.sin(s.rotation) * back, s.position[1], s.position[2] - Math.cos(s.rotation) * back);
    o.rotation.y = s.rotation;
    group.add(o);
  }
}

export function disposeGroup(g: THREE.Object3D): void {
  g.traverse((o) => {
    const m = o as THREE.Mesh;
    m.geometry?.dispose?.();
    const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : [];
    for (const mt of mats) { (mt as THREE.MeshStandardMaterial).map?.dispose?.(); mt.dispose?.(); }
  });
  g.parent?.remove(g);
}
