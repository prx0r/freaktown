/**
 * MicStand — a straight club mic stand with a short boom and a ball-grille
 * mic, fitted to the performer's mouth (StageRuntime calls fitTo() once the
 * body is loaded). The capsule sits a little below and in front of the
 * mouth, aimed at it, so the comic visibly works the mic; lean-ins on
 * punchlines bring the mouth onto it.
 *
 * Geometry is local to `group` (feet at y=0); everything is procedural.
 */

import * as THREE from 'three';

export interface MicFit {
  /** Forward gap mouth → grille centre at rest (m). */
  forward: number;
  /** Grille centre below the mouth (m). */
  below: number;
  /** Sideways offset toward the performer's left (+x), keeps the lips clear on centred cameras. */
  side: number;
}

export const DEFAULT_MIC_FIT: MicFit = { forward: 0.12, below: 0.042, side: 0.015 };

export class MicStand {
  readonly group = new THREE.Group();
  /** World-space grille centre (read by tests/telemetry). */
  readonly capsule = new THREE.Object3D();
  private pole: THREE.Mesh;
  private clutch: THREE.Mesh;
  private boom: THREE.Mesh;
  private head = new THREE.Group();
  private cable: THREE.Mesh | null = null;
  private cableMat: THREE.MeshStandardMaterial;

  constructor() {
    const metal = new THREE.MeshStandardMaterial({ color: 0x1b1b1e, metalness: 0.85, roughness: 0.32 });
    const chrome = new THREE.MeshStandardMaterial({ color: 0xb8bcc4, metalness: 1, roughness: 0.22 });
    this.cableMat = new THREE.MeshStandardMaterial({ color: 0x0c0c0e, roughness: 0.7 });

    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.17, 0.025, 32), metal);
    base.position.y = 0.0125;
    this.pole = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 1, 12), metal);
    this.clutch = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.05, 12), metal);
    this.boom = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 1, 10), metal);

    // SM58-style mic: tapered black handle + chrome ball grille, built along +Y (grille end at +Y).
    const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.013, 0.15, 18), new THREE.MeshStandardMaterial({ color: 0x141416, metalness: 0.4, roughness: 0.45 }));
    handle.position.y = -0.075;
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.012, 18), chrome);
    ring.position.y = 0.004;
    const grilleTex = (() => {
      const c = document.createElement('canvas'); c.width = c.height = 64;
      const g = c.getContext('2d')!;
      g.fillStyle = '#9aa0a8'; g.fillRect(0, 0, 64, 64);
      g.strokeStyle = '#3a3d44'; g.lineWidth = 2;
      for (let i = -64; i < 128; i += 6) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 64, 64); g.stroke(); g.beginPath(); g.moveTo(i + 64, 0); g.lineTo(i, 64); g.stroke(); }
      const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(4, 2); return t;
    })();
    const grille = new THREE.Mesh(new THREE.SphereGeometry(0.027, 24, 16), new THREE.MeshStandardMaterial({ map: grilleTex, metalness: 0.9, roughness: 0.35 }));
    grille.position.y = 0.03;
    this.head.add(handle, ring, grille);
    this.capsule.position.y = 0.03;
    this.head.add(this.capsule);

    for (const m of [base, this.pole, this.clutch, this.boom, handle, ring, grille]) m.castShadow = true;
    this.group.add(base, this.pole, this.clutch, this.boom, this.head);
    this.group.name = 'mic-stand';
  }

  /**
   * Place the stand for a mouth at `mouth` (world, performer facing +Z).
   * The base goes on the floor in front of the performer; the boom angles
   * up-and-back so the grille ends up `fit.forward` in front of the lips.
   */
  fitTo(mouth: THREE.Vector3, fit: MicFit = DEFAULT_MIC_FIT): void {
    const grille = new THREE.Vector3(mouth.x + fit.side, mouth.y - fit.below, mouth.z + fit.forward);
    // mic body points from below-front up at the mouth
    const aim = mouth.clone().sub(grille).normalize();
    const micTail = grille.clone().addScaledVector(aim, -0.17); // end of the handle
    // stand stands further forward; boom joins the handle tail
    const baseXZ = new THREE.Vector3(grille.x + 0.02, 0, grille.z + 0.24);
    const clutchY = Math.max(0.5, micTail.y - 0.1);
    this.group.position.set(0, 0, 0);

    this.pole.scale.y = clutchY;
    this.pole.position.set(baseXZ.x, clutchY / 2, baseXZ.z);
    this.clutch.position.set(baseXZ.x, clutchY, baseXZ.z);
    const top = new THREE.Vector3(baseXZ.x, clutchY, baseXZ.z);
    const boomVec = micTail.clone().sub(top);
    this.boom.scale.y = boomVec.length();
    this.boom.position.copy(top).addScaledVector(boomVec, 0.5);
    this.boom.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), boomVec.clone().normalize());

    // mic head: local +Y along aim, grille centre (local y 0.03) at `grille`
    this.head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), aim);
    this.head.position.copy(grille).addScaledVector(aim, -0.03);

    // cable: from the handle tail down the pole to the floor and off upstage
    if (this.cable) { this.group.remove(this.cable); this.cable.geometry.dispose(); }
    const pts = [
      micTail.clone(), new THREE.Vector3(baseXZ.x + 0.02, clutchY - 0.05, baseXZ.z - 0.01),
      new THREE.Vector3(baseXZ.x + 0.025, clutchY * 0.5, baseXZ.z - 0.015),
      new THREE.Vector3(baseXZ.x + 0.05, 0.02, baseXZ.z - 0.1),
      new THREE.Vector3(baseXZ.x + 0.5, 0.012, baseXZ.z - 0.7), new THREE.Vector3(baseXZ.x + 1.6, 0.012, baseXZ.z - 1.4),
    ];
    this.cable = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, 0.0045, 6), this.cableMat);
    this.group.add(this.cable);
    this.group.updateMatrixWorld(true);
  }

  /** World position of the grille centre. */
  grilleWorld(out = new THREE.Vector3()): THREE.Vector3 {
    this.group.updateMatrixWorld(true);
    return this.capsule.getWorldPosition(out);
  }
}
