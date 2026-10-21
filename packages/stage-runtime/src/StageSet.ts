/**
 * StageSet — the comedy-club room: brick backdrop + neon sign, stage deck,
 * mic stand, curtains, spot/rim/foot lights and a seated audience.
 * All procedural (canvas textures, primitives): no binary assets to ship.
 */

import * as THREE from 'three';

export interface StageSetOptions {
  sign?: string;
  /** Rows × seats of audience silhouettes. */
  audienceRows?: number;
  audienceSeats?: number;
  shadows?: boolean;
}

function canvasTexture(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d')!;
  draw(ctx);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function brickTexture(): THREE.CanvasTexture {
  const tex = canvasTexture(1024, 512, (ctx) => {
    ctx.fillStyle = '#2a1512';
    ctx.fillRect(0, 0, 1024, 512);
    const bw = 64, bh = 28;
    let seed = 11;
    const r = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
    for (let y = 0; y < 512; y += bh) {
      const off = (y / bh) % 2 ? bw / 2 : 0;
      for (let x = -bw; x < 1024 + bw; x += bw) {
        const l = 28 + r() * 16;
        ctx.fillStyle = `hsl(${8 + r() * 10}, ${45 + r() * 15}%, ${l}%)`;
        ctx.fillRect(x + off + 2, y + 2, bw - 4, bh - 4);
      }
    }
  });
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(3, 2);
  return tex;
}

function neonTexture(text: string): THREE.CanvasTexture {
  return canvasTexture(1024, 256, (ctx) => {
    ctx.clearRect(0, 0, 1024, 256);
    ctx.font = 'bold 150px "Arial Black", Impact, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = '#ff2fa0';
    ctx.shadowBlur = 40;
    ctx.strokeStyle = '#ff7ac8';
    ctx.lineWidth = 10;
    ctx.strokeText(text, 512, 130);
    ctx.shadowBlur = 18;
    ctx.fillStyle = '#ffe6f4';
    ctx.fillText(text, 512, 130);
  });
}

function woodTexture(): THREE.CanvasTexture {
  const tex = canvasTexture(512, 512, (ctx) => {
    for (let i = 0; i < 16; i++) {
      ctx.fillStyle = `hsl(25, 35%, ${14 + (i % 3) * 3}%)`;
      ctx.fillRect(0, i * 32, 512, 31);
    }
    ctx.globalAlpha = 0.15;
    for (let i = 0; i < 400; i++) {
      ctx.fillStyle = i % 2 ? '#000' : '#5a3a20';
      ctx.fillRect(Math.random() * 512, Math.random() * 512, 40 + Math.random() * 80, 1);
    }
  });
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  return tex;
}

export class StageSet {
  readonly group = new THREE.Group();
  readonly spot: THREE.SpotLight;
  private beam: THREE.Mesh;
  private audience: THREE.InstancedMesh;
  private audienceBase: THREE.Matrix4[] = [];
  private houseLight: THREE.PointLight;
  private signMat: THREE.MeshBasicMaterial;
  private excitement = 0;
  private rims: THREE.SpotLight[] = [];

  constructor(scene: THREE.Scene, opts: StageSetOptions = {}) {
    scene.add(this.group);
    scene.fog = new THREE.Fog(0x05030a, 9, 22);

    // stage deck (top at y=0), house floor lower
    const deck = new THREE.Mesh(new THREE.BoxGeometry(9, 0.6, 4.6), new THREE.MeshStandardMaterial({ map: woodTexture(), roughness: 0.75 }));
    deck.position.set(0, -0.3, -0.1);
    deck.receiveShadow = true;
    this.group.add(deck);
    const lip = new THREE.Mesh(new THREE.BoxGeometry(9, 0.06, 0.06), new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0x331122 }));
    lip.position.set(0, 0.0, 2.2);
    this.group.add(lip);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.MeshStandardMaterial({ color: 0x0b0810, roughness: 1 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.6;
    floor.receiveShadow = true;
    this.group.add(floor);

    // brick back wall
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 7), new THREE.MeshStandardMaterial({ map: brickTexture(), roughness: 0.95 }));
    wall.position.set(0, 2.9, -2.3);
    wall.receiveShadow = true;
    this.group.add(wall);

    // neon sign
    this.signMat = new THREE.MeshBasicMaterial({ map: neonTexture(opts.sign ?? 'FREAK TOWN'), transparent: true, depthWrite: false, toneMapped: false });
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(4, 1), this.signMat);
    sign.position.set(0, 3.25, -2.25);
    this.group.add(sign);
    const signGlow = new THREE.PointLight(0xff3fa8, 6, 6, 2);
    signGlow.position.set(0, 3.2, -1.6);
    this.group.add(signGlow);

    // curtains
    const curtainMat = new THREE.MeshStandardMaterial({ color: 0x6a0d1a, roughness: 0.85, side: THREE.DoubleSide });
    for (const side of [-1, 1]) {
      const geo = new THREE.PlaneGeometry(2.2, 6.5, 40, 1);
      const pos = geo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < pos.count; i++) pos.setZ(i, Math.sin(pos.getX(i) * 9) * 0.12);
      geo.computeVertexNormals();
      const c = new THREE.Mesh(geo, curtainMat);
      c.position.set(side * 4.3, 2.65, -1.2);
      c.rotation.y = -side * 0.35;
      c.receiveShadow = true;
      this.group.add(c);
    }

    // mic stand (stage-left of the performer so close-ups stay clear)
    const metal = new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.9, roughness: 0.3 });
    const stand = new THREE.Group();
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.03, 24), metal);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.38, 10), metal);
    pole.position.y = 0.7;
    const boom = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.009, 0.3, 8), metal);
    boom.position.set(-0.08, 1.42, 0.08);
    boom.rotation.set(0.9, 0, 0.6);
    const mic = new THREE.Mesh(new THREE.SphereGeometry(0.03, 14, 10), new THREE.MeshStandardMaterial({ color: 0x777777, metalness: 0.6, roughness: 0.5 }));
    mic.position.set(-0.17, 1.5, 0.17);
    for (const m of [base, pole, boom, mic]) { m.castShadow = true; stand.add(m); }
    stand.position.set(0.42, 0, 0.45);
    this.group.add(stand);

    // stool behind for depth
    const stool = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.05, 20), new THREE.MeshStandardMaterial({ color: 0x3a2a20 }));
    seat.position.y = 0.75;
    stool.add(seat);
    for (let i = 0; i < 3; i++) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.75, 6), metal);
      const a = (i / 3) * Math.PI * 2;
      leg.position.set(Math.cos(a) * 0.14, 0.37, Math.sin(a) * 0.14);
      stool.add(leg);
    }
    stool.position.set(-1.3, 0, -0.9);
    stool.traverse((o) => { (o as THREE.Mesh).castShadow = true; });
    this.group.add(stool);

    // lights
    scene.add(new THREE.HemisphereLight(0x3a3060, 0x100808, 0.55));
    this.spot = new THREE.SpotLight(0xfff0dc, 70, 14, 0.38, 0.45, 1.6);
    this.spot.position.set(0, 6.2, 4.2);
    this.spot.target.position.set(0, 1.0, 0);
    this.spot.castShadow = opts.shadows ?? true;
    this.spot.shadow.mapSize.set(1024, 1024);
    this.spot.shadow.bias = -0.0005;
    this.group.add(this.spot, this.spot.target);
    const fill = new THREE.DirectionalLight(0xd8e4ff, 0.35);
    fill.position.set(-3, 2.5, 4);
    this.group.add(fill);
    for (const [x, color] of [[-3.2, 0x40d0ff], [3.2, 0xff40c0]] as const) {
      const rim = new THREE.SpotLight(color, 40, 10, 0.5, 0.6, 1.5);
      rim.position.set(x, 4.2, -1.6);
      rim.target.position.set(0, 1.3, 0);
      this.group.add(rim, rim.target);
      this.rims.push(rim);
    }
    this.houseLight = new THREE.PointLight(0xffb070, 0, 12, 2);
    this.houseLight.position.set(0, 3.5, 5);
    this.group.add(this.houseLight);

    // visible spot beam
    const beamGeo = new THREE.ConeGeometry(1.25, 6.6, 32, 1, true);
    beamGeo.translate(0, -3.3, 0);
    this.beam = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({
      color: 0xfff1d6, transparent: true, opacity: 0.05, blending: THREE.AdditiveBlending,
      depthWrite: false, side: THREE.DoubleSide,
    }));
    this.beam.position.copy(this.spot.position);
    this.beam.lookAt(new THREE.Vector3(0, -0.5, -0.2));
    this.beam.rotateX(-Math.PI / 2);
    this.group.add(this.beam);

    // footlights
    for (let i = -3; i <= 3; i++) {
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffd28a, toneMapped: false }));
      bulb.position.set(i * 1.1, 0.04, 2.15);
      this.group.add(bulb);
    }

    // audience: seated silhouettes (head+shoulders as one capsule instance)
    const rows = opts.audienceRows ?? 4;
    const seats = opts.audienceSeats ?? 11;
    const geo = new THREE.CapsuleGeometry(0.2, 0.35, 4, 10);
    const am = new THREE.MeshStandardMaterial({ color: 0x07060a, roughness: 1 });
    this.audience = new THREE.InstancedMesh(geo, am, rows * seats);
    let n = 0;
    const m = new THREE.Matrix4();
    for (let r = 0; r < rows; r++) {
      for (let s = 0; s < seats; s++) {
        const x = (s - (seats - 1) / 2) * 0.72 + (r % 2 ? 0.36 : 0) + Math.sin(n * 12.9898) * 0.08;
        const z = 3.0 + r * 0.95;
        const y = -0.05 + r * 0.18;
        const sc = 0.9 + ((n * 7) % 5) * 0.04;
        m.compose(new THREE.Vector3(x, y, z), new THREE.Quaternion(), new THREE.Vector3(sc, sc, sc));
        this.audience.setMatrixAt(n, m);
        this.audienceBase.push(m.clone());
        n++;
      }
    }
    this.group.add(this.audience);
  }

  /** Crowd energy 0..1 (laughs/claps): audience bobs, house lights warm up. */
  excite(amount: number): void {
    this.excitement = Math.min(1.5, this.excitement + amount);
  }

  update(dt: number, wallMs: number): void {
    this.excitement = Math.max(0, this.excitement - dt * 0.6);
    const e = this.excitement;
    this.houseLight.intensity = e * 8;
    this.signMat.opacity = 0.85 + 0.15 * Math.sin(wallMs * 0.013) * Math.sin(wallMs * 0.0021);
    const m = new THREE.Matrix4();
    const v = new THREE.Vector3();
    for (let i = 0; i < this.audienceBase.length; i++) {
      m.copy(this.audienceBase[i]);
      const bob = e > 0.01 ? Math.abs(Math.sin(wallMs * 0.012 + i * 1.7)) * 0.06 * e : 0;
      v.setFromMatrixPosition(m);
      m.setPosition(v.x, v.y + bob, v.z);
      this.audience.setMatrixAt(i, m);
    }
    this.audience.instanceMatrix.needsUpdate = true;
    for (const [i, rim] of this.rims.entries()) rim.intensity = 40 + 25 * e * Math.abs(Math.sin(wallMs * 0.006 + i));
  }
}
