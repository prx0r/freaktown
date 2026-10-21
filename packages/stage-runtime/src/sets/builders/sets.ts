/**
 * Procedural set builders — every set renders with zero downloads.
 * comedy-club reuses StageSet (the original room); the rest are built here.
 */
import * as THREE from 'three';
import { StageSet } from '../../StageSet';
import type { SetDefinition } from '../types';
import { seatLocal } from '../camera';
import {
  applyLighting, box, canvasTexture, chair, cyl, disposeGroup, glow, placeAtSeats, redraw, std,
  type BuildContext, type BuiltSet,
} from './common';

export type SetBuilder = (def: SetDefinition, ctx: BuildContext) => BuiltSet;

// ── comedy club ──
const comedyClub: SetBuilder = (_def, ctx) => {
  const group = new THREE.Group();
  const stage = new StageSet(group as unknown as THREE.Scene, { shadows: ctx.shadows });
  return { group, update: (dt, w) => stage.update(dt, w), dispose: () => disposeGroup(group) };
};

// ── news studio ──
function drawHeadline(ctx: CanvasRenderingContext2D, text: string, kicker: string, t = 0): void {
  const W = ctx.canvas.width, H = ctx.canvas.height;
  const g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, '#071a3d'); g.addColorStop(0.6, '#0c3a8c'); g.addColorStop(1, '#03122b');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.globalAlpha = 0.12; ctx.fillStyle = '#7fb2ff';
  for (let i = 0; i < 14; i++) ctx.fillRect(((i * 97 + t * 40) % (W + 200)) - 200, (i * 53) % H, 180, 3);
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#e8112d'; ctx.fillRect(48, 54, 150, 46);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 30px Inter, Arial, sans-serif'; ctx.fillText('LIVE', 78, 88);
  ctx.fillStyle = '#ffcc33'; ctx.font = 'bold 34px Inter, Arial, sans-serif'; ctx.fillText(kicker.toUpperCase(), 230, 88);
  ctx.fillStyle = '#ffffff'; ctx.font = 'bold 64px Inter, Arial, sans-serif';
  const words = text.split(/\s+/); let line = ''; let y = 220;
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > W - 110 && line) { ctx.fillText(line, 52, y); line = w; y += 78; } else line = test;
  }
  if (line) ctx.fillText(line, 52, y);
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = 'bold 28px Inter, Arial, sans-serif'; ctx.fillText('FREAK TOWN NEWS', 52, H - 40);
}

const newsStudio: SetBuilder = (def, ctx) => {
  const group = new THREE.Group();
  applyLighting(group, def.lighting, ctx);
  // floor + riser
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), std(0x0b1426, 0.35, 0.3));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; group.add(floor);
  const riser = cyl(2.6, 2.7, 0.06, std(0x162544, 0.4, 0.3), 0, 0.03, -0.6, 48); riser.scale.z = 0.55; group.add(riser);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.65, 0.02, 6, 64), glow(0x2f7bff)); ring.rotation.x = Math.PI / 2; ring.scale.y = 0.55; ring.position.set(0, 0.06, -0.6); group.add(ring);
  // cyclorama
  const cycTex = canvasTexture(512, 256, (c) => { const g = c.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, '#0a1a3a'); g.addColorStop(1, '#1d4fae'); c.fillStyle = g; c.fillRect(0, 0, 512, 256); });
  const cyc = new THREE.Mesh(new THREE.CylinderGeometry(7.5, 7.5, 7, 48, 1, true, Math.PI * 0.6, Math.PI * 0.8), new THREE.MeshBasicMaterial({ map: cycTex, side: THREE.BackSide }));
  cyc.position.set(0, 3.5, 1.5); group.add(cyc);
  // video wall
  const wallTex = canvasTexture(1024, 512, (c) => drawHeadline(c, 'Freak Town News — tonight', 'top story'));
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 2.6), new THREE.MeshBasicMaterial({ map: wallTex, toneMapped: false }));
  wall.position.set(0, 2.05, -2.7); group.add(wall);
  group.add(box(5.4, 2.8, 0.08, std(0x05080f, 0.4, 0.6), 0, 2.05, -2.76));
  for (const x of [-3.6, 3.6]) {
    const side = box(1.4, 3.2, 0.1, std(0x0d1f44, 0.5, 0.2, 0x0a2a6a, 0.5), x, 1.6, -2.4); side.rotation.y = x > 0 ? -0.35 : 0.35; group.add(side);
    group.add(box(0.06, 3.0, 0.12, glow(0x3c8cff), x * 0.82, 1.6, -2.5));
  }
  // desk (front panel with logo)
  const logoTex = canvasTexture(1024, 256, (c) => {
    const g = c.createLinearGradient(0, 0, 1024, 0); g.addColorStop(0, '#0a2a6a'); g.addColorStop(0.5, '#1960e0'); g.addColorStop(1, '#0a2a6a');
    c.fillStyle = g; c.fillRect(0, 0, 1024, 256); c.fillStyle = '#fff'; c.font = 'bold 96px Inter, Arial, sans-serif'; c.textAlign = 'center'; c.fillText('FREAK NEWS', 512, 160);
    c.fillStyle = '#ffcc33'; c.fillRect(0, 222, 1024, 10);
  });
  const deskFront = new THREE.Mesh(new THREE.CylinderGeometry(2.0, 1.9, 0.78, 48, 1, true, -0.62, 1.24), [new THREE.MeshStandardMaterial({ map: logoTex, emissive: 0xffffff, emissiveMap: logoTex, emissiveIntensity: 0.35, roughness: 0.4, side: THREE.DoubleSide })]);
  deskFront.position.set(0, 0.39, -1.75); group.add(deskFront);
  const top = new THREE.Mesh(new THREE.RingGeometry(1.5, 2.12, 48, 1, -Math.PI / 2 - 0.66, 1.32), new THREE.MeshStandardMaterial({ color: 0xe9eef7, roughness: 0.25, metalness: 0.1, side: THREE.DoubleSide }));
  top.rotation.x = -Math.PI / 2; top.position.set(0, 0.8, -1.8); group.add(top);
  // chairs + papers + laptop
  placeAtSeats(def, () => chair(std(0x1a1a1f, 0.5, 0.2)), group, 0.05);
  for (const s of def.seats) {
    const paper = box(0.21, 0.004, 0.29, std(0xffffff, 0.9), s.position[0] - 0.1, 0.81, -0.05); paper.rotation.y = 0.1; group.add(paper);
  }
  const laptop = box(0.34, 0.02, 0.24, std(0x9aa3ad, 0.3, 0.8), 0, 0.82, -0.02); group.add(laptop);
  // studio cameras (props) + light grid
  for (const x of [-3.4, 3.4]) {
    const cam = new THREE.Group();
    cam.add(cyl(0.05, 0.05, 1.3, std(0x333333, 0.4, 0.6), 0, 0.65, 0, 8));
    cam.add(box(0.32, 0.3, 0.6, std(0x202226, 0.5, 0.4), 0, 1.4, 0));
    cam.add(box(0.22, 0.16, 0.02, glow(0x88aaff), 0, 1.45, 0.31));
    cam.position.set(x, 0, 3.4); cam.lookAt(0, 0, -1); group.add(cam);
  }
  for (let i = -3; i <= 3; i++) group.add(box(0.25, 0.12, 0.25, glow(i % 2 ? 0xfff2d0 : 0xcfe0ff), i * 1.1, 4.3, 0.5));
  let t = 0; let headline = 'Freak Town News — tonight'; let kicker = 'top story';
  return {
    group,
    update: (dt) => { t += dt; if (Math.floor(t * 4) !== Math.floor((t - dt) * 4)) redraw(wallTex, (c) => drawHeadline(c, headline, kicker, t)); },
    setHeadline: (text, k = 'breaking') => { headline = text; kicker = k; redraw(wallTex, (c) => drawHeadline(c, headline, kicker, t)); },
    dispose: () => disposeGroup(group),
  };
};

// ── podcast ──
const podcast: SetBuilder = (def, ctx) => {
  const group = new THREE.Group();
  applyLighting(group, def.lighting, ctx);
  const woodTex = canvasTexture(512, 512, (c) => {
    c.fillStyle = '#5a3a22'; c.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 16; i++) { c.fillStyle = i % 2 ? '#64412a' : '#4e321e'; c.fillRect(0, i * 32, 512, 30); }
  });
  woodTex.wrapS = woodTex.wrapT = THREE.RepeatWrapping; woodTex.repeat.set(6, 6);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({ map: woodTex, roughness: 0.7 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; group.add(floor);
  const rug = cyl(2.2, 2.2, 0.01, std(0x2b3a4a, 0.95), 0, 0.005, -0.2, 48); group.add(rug);
  // back + side walls with acoustic panels
  group.add(box(12, 4.5, 0.1, std(0x231a16, 0.9), 0, 2.25, -3.2));
  for (const x of [-4.2, 4.2]) group.add(box(0.1, 4.5, 8, std(0x231a16, 0.9), x, 2.25, 0.5));
  const panelCols = [0x3b2a4d, 0x22333f, 0x5a2d2d];
  for (let r = 0; r < 3; r++) for (let c = -4; c <= 4; c++) {
    const p = box(0.62, 0.62, 0.08, std(panelCols[(r + c + 9) % 3], 0.98), c * 0.72, 1.0 + r * 0.72, -3.1);
    group.add(p);
  }
  for (const x of [-4.1, 4.1]) for (let r = 0; r < 2; r++) for (let z = -2; z <= 1; z++) group.add(box(0.08, 0.62, 0.62, std(panelCols[(r + z + 6) % 3], 0.98), x * 0.98, 1.2 + r * 0.72, z * 0.75));
  // ON AIR sign
  const onTex = canvasTexture(512, 160, (c) => { c.fillStyle = '#1a0000'; c.fillRect(0, 0, 512, 160); c.fillStyle = '#ff2424'; c.font = 'bold 110px Inter, Arial, sans-serif'; c.textAlign = 'center'; c.fillText('ON AIR', 256, 120); });
  const onMat = new THREE.MeshBasicMaterial({ map: onTex, toneMapped: false });
  const sign = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.4), onMat); sign.position.set(0, 3.45, -3.12); group.add(sign);
  group.add(box(1.4, 0.5, 0.06, std(0x111111, 0.4, 0.6), 0, 3.45, -3.17));
  // round table
  const tableTop = cyl(0.82, 0.82, 0.05, std(0x2a1d14, 0.35, 0.1), 0, 0.75, 0, 48); tableTop.castShadow = true; group.add(tableTop);
  group.add(new THREE.Mesh(new THREE.TorusGeometry(0.82, 0.012, 6, 64), glow(0xff5a8a)).translateY(0.725).rotateX(Math.PI / 2));
  group.add(cyl(0.08, 0.1, 0.72, std(0x111111, 0.4, 0.7), 0, 0.36, 0, 12));
  group.add(cyl(0.4, 0.4, 0.03, std(0x111111, 0.4, 0.7), 0, 0.015, 0, 24));
  // chairs, boom-arm mics, headphones, mugs
  placeAtSeats(def, () => chair(std(0x1d1d22, 0.6, 0.2)), group, 0.08);
  const metal = std(0x1b1b1b, 0.35, 0.8);
  for (const s of def.seats) {
    const toward = (k: number): THREE.Vector3 => new THREE.Vector3(s.position[0] * k, 0, s.position[2] * k);
    const clamp = toward(0.8 / 1.2 * 0.92); // table edge in front of the seat
    const mount = cyl(0.025, 0.025, 0.45, metal, clamp.x, 0.98, clamp.z, 8); group.add(mount);
    const [mx, my, mz] = seatLocal(s, [0.0, -0.12, 0.3]);
    const elbow = new THREE.Vector3(clamp.x * 0.85 + mx * 0.15, 1.38, clamp.z * 0.85 + mz * 0.15);
    const arm = (a: THREE.Vector3, b: THREE.Vector3) => {
      const len = a.distanceTo(b);
      const m = cyl(0.012, 0.012, len, metal, 0, 0, 0, 6);
      m.position.copy(a).add(b).multiplyScalar(0.5);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
      group.add(m);
    };
    const top = new THREE.Vector3(clamp.x, 1.2, clamp.z);
    const mic = new THREE.Vector3(mx, my, mz);
    arm(top, elbow); arm(elbow, mic);
    const capsule = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.11, 4, 10), std(0x2a2a2e, 0.3, 0.6));
    capsule.position.copy(mic); capsule.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), mic.clone().sub(elbow).normalize()); group.add(capsule);
    // headphones resting on the table + mug
    const hp = new THREE.Group();
    hp.add(new THREE.Mesh(new THREE.TorusGeometry(0.085, 0.012, 6, 20, Math.PI), std(0x111111, 0.5, 0.3)));
    for (const x of [-0.085, 0.085]) hp.add(cyl(0.04, 0.04, 0.03, std(0x111111, 0.5, 0.3), x, 0, 0, 12).rotateZ(Math.PI / 2));
    const hpPos = toward(0.5); hp.position.set(hpPos.x + 0.12, 0.8, hpPos.z); hp.rotation.x = -Math.PI / 2; hp.rotation.z = s.rotation; group.add(hp);
    const mugP = toward(0.48); group.add(cyl(0.04, 0.035, 0.1, std(0xeeeeee, 0.4), mugP.x - 0.14, 0.83, mugP.z, 12));
  }
  // practical lamp
  group.add(cyl(0.02, 0.02, 1.6, metal, 3.0, 0.8, -2.4, 8));
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), glow(0xffd9a0)); lamp.position.set(3.0, 1.7, -2.4); group.add(lamp);
  let on = true; let t = 0;
  return {
    group,
    update: (dt) => { t += dt; onMat.color.setScalar(on ? 0.85 + Math.sin(t * 3) * 0.15 : 0.25); },
    setOnAir: (v) => { on = v; },
    dispose: () => disposeGroup(group),
  };
};

// ── poker table ──
export const POKER_TOP_Y = 0.8;
const pokerTable: SetBuilder = (def, ctx) => {
  const group = new THREE.Group();
  applyLighting(group, def.lighting, ctx);
  const carpet = canvasTexture(256, 256, (c) => {
    c.fillStyle = '#3a0d12'; c.fillRect(0, 0, 256, 256);
    c.strokeStyle = '#6a1a22'; c.lineWidth = 6; for (let i = 0; i < 8; i++) { c.beginPath(); c.arc(i % 2 ? 64 : 192, (i * 32) % 256, 40, 0, Math.PI * 2); c.stroke(); }
    c.fillStyle = '#c49a3a'; for (let i = 0; i < 10; i++) c.fillRect((i * 53) % 256, (i * 91) % 256, 6, 6);
  });
  carpet.wrapS = carpet.wrapT = THREE.RepeatWrapping; carpet.repeat.set(8, 8);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(24, 24), new THREE.MeshStandardMaterial({ map: carpet, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; group.add(floor);
  // oval table: 3.0 × 1.4 m felt inside a padded rail, top at 0.8
  const felt = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 0.06, 64), std(0x0f6b3a, 0.95)); felt.scale.set(1.5, 1, 0.72); felt.position.y = POKER_TOP_Y - 0.03; felt.receiveShadow = true; group.add(felt);
  const lineMat = new THREE.MeshBasicMaterial({ color: 0xc8e6c9, transparent: true, opacity: 0.35 });
  const betLine = new THREE.Mesh(new THREE.RingGeometry(0.62, 0.635, 64), lineMat); betLine.rotation.x = -Math.PI / 2; betLine.scale.set(1.5, 0.72, 1); betLine.position.y = POKER_TOP_Y + 0.002; group.add(betLine);
  const rail = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.09, 12, 72), std(0x121212, 0.45, 0.1)); rail.rotation.x = Math.PI / 2; rail.scale.set(1.55, 0.76, 1); rail.position.y = POKER_TOP_Y; rail.castShadow = true; group.add(rail);
  const apron = new THREE.Mesh(new THREE.CylinderGeometry(1, 0.94, 0.16, 64, 1, true), std(0x3a2414, 0.6)); apron.scale.set(1.55, 1, 0.76); apron.position.y = POKER_TOP_Y - 0.12; group.add(apron);
  group.add(box(0.5, 0.72, 0.4, std(0x1a1a1a, 0.5, 0.4), -0.6, 0.36, 0));
  group.add(box(0.5, 0.72, 0.4, std(0x1a1a1a, 0.5, 0.4), 0.6, 0.36, 0));
  // dealer tray (far side, -Z)
  group.add(box(0.5, 0.03, 0.12, std(0x222222, 0.4, 0.6), 0, POKER_TOP_Y + 0.01, -0.62));
  // felt logo
  const logo = canvasTexture(512, 128, (c) => { c.clearRect(0, 0, 512, 128); c.fillStyle = 'rgba(255,240,180,0.55)'; c.font = 'bold 64px Georgia, serif'; c.textAlign = 'center'; c.fillText('FREAK TOWN', 256, 86); });
  const logoMesh = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.22), new THREE.MeshBasicMaterial({ map: logo, transparent: true, depthWrite: false }));
  logoMesh.rotation.x = -Math.PI / 2; logoMesh.position.set(0, POKER_TOP_Y + 0.003, 0.4); group.add(logoMesh);
  placeAtSeats(def, () => chair(std(0x2a1010, 0.6, 0.1)), group, 0.12);
  // hanging lamp
  const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.9, 0.35, 32, 1, true), std(0x0d3a1c, 0.5, 0.3, 0x000000)); shade.position.set(0, 2.55, 0); shade.scale.z = 0.6; group.add(shade);
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8), glow(0xfff1c0)); bulb.position.set(0, 2.45, 0); group.add(bulb);
  group.add(cyl(0.01, 0.01, 1.5, std(0x111111), 0, 3.4, 0, 6));
  const pool = new THREE.PointLight(0xfff0c8, ctx.low ? 6 : 10, 4, 1.5); pool.position.set(0, 2.3, 0); group.add(pool);
  // dark walls far back
  group.add(box(16, 4, 0.1, std(0x120a08, 0.9), 0, 2, -5));
  return { group, update: () => {}, dispose: () => disposeGroup(group) };
};

export const SET_BUILDERS: Record<string, SetBuilder> = {
  'comedy-club': comedyClub,
  'news-studio': newsStudio,
  podcast,
  'poker-table': pokerTable,
};
