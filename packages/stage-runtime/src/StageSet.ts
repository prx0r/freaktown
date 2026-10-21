/**
 * StageSet — the comedy-club room: brick backdrop + neon sign, stage deck,
 * mic stand, curtains, spot/rim/foot lights and a seated audience.
 * All procedural (canvas textures, primitives): no binary assets to ship.
 */

import * as THREE from 'three';
import { MicStand } from './MicStand';

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

/** Brick + mortar colour map and a matching bump map (mortar recessed). */
function brickTextures(): { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
  const W = 1024, H = 512, bw = 96, bh = 40, mortar = 5;
  let seed = 11;
  const r = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  const bricks: Array<[number, number, number]> = [];
  for (let y = 0; y < H; y += bh) {
    const off = (y / bh) % 2 ? bw / 2 : 0;
    for (let x = -bw; x < W + bw; x += bw) bricks.push([x + off, y, r()]);
  }
  const map = canvasTexture(W, H, (ctx) => {
    ctx.fillStyle = '#6b5a52'; // mortar
    ctx.fillRect(0, 0, W, H);
    for (const [x, y, k] of bricks) {
      const l = 30 + k * 16;
      ctx.fillStyle = `hsl(${9 + k * 9}, ${48 + k * 14}%, ${l}%)`;
      ctx.fillRect(x + mortar / 2, y + mortar / 2, bw - mortar, bh - mortar);
      // face grain + soot at the top edge
      ctx.globalAlpha = 0.18;
      for (let i = 0; i < 14; i++) {
        ctx.fillStyle = i % 2 ? '#000' : '#ffd0b0';
        ctx.fillRect(x + mortar + r() * (bw - 2 * mortar - 6), y + mortar + r() * (bh - 2 * mortar - 3), 2 + r() * 6, 1 + r() * 2);
      }
      ctx.globalAlpha = 0.25;
      ctx.fillStyle = '#1a0805';
      ctx.fillRect(x + mortar / 2, y + mortar / 2, bw - mortar, 3);
      ctx.globalAlpha = 1;
    }
  });
  const bump = canvasTexture(W, H, (ctx) => {
    ctx.fillStyle = '#202020';
    ctx.fillRect(0, 0, W, H);
    for (const [x, y, k] of bricks) {
      ctx.fillStyle = `rgb(${200 + k * 40},${200 + k * 40},${200 + k * 40})`;
      ctx.fillRect(x + mortar / 2 + 1, y + mortar / 2 + 1, bw - mortar - 2, bh - mortar - 2);
    }
  });
  for (const t of [map, bump]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 2.2); }
  bump.colorSpace = THREE.NoColorSpace;
  return { map, bump };
}

/** Soft radial puff for the haze sprites. */
function hazeTexture(): THREE.CanvasTexture {
  return canvasTexture(256, 256, (ctx) => {
    const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, 'rgba(255,255,255,0.55)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.18)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 256);
  });
}

/** Additive light-cone material: bright at the lamp, fading toward the floor and at the rim. */
function beamMaterial(color: number, strength: number): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uStrength: { value: strength } },
    vertexShader: `varying float vY; varying vec3 vN; varying vec3 vV;
      void main(){ vY = uv.y; vec4 mv = modelViewMatrix * vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform vec3 uColor; uniform float uStrength; varying float vY; varying vec3 vN; varying vec3 vV;
      void main(){ float edge = pow(abs(dot(vN, vV)), 1.6); float along = mix(0.25, 1.0, vY); gl_FragColor = vec4(uColor * uStrength * edge * along, 1.0); }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
  });
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

/** Minimal non-indexed merge of two geometries (avoids pulling in examples/ utils). */
function mergeGeometries(a: THREE.BufferGeometry, b: THREE.BufferGeometry): THREE.BufferGeometry {
  const A = a.index ? a.toNonIndexed() : a;
  const B = b.index ? b.toNonIndexed() : b;
  const out = new THREE.BufferGeometry();
  for (const name of ['position', 'normal']) {
    const x = A.getAttribute(name) as THREE.BufferAttribute, y = B.getAttribute(name) as THREE.BufferAttribute;
    const arr = new Float32Array(x.array.length + y.array.length);
    arr.set(x.array as Float32Array, 0); arr.set(y.array as Float32Array, x.array.length);
    out.setAttribute(name, new THREE.BufferAttribute(arr, 3));
  }
  return out;
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
  readonly mic: MicStand;
  private haze: THREE.Sprite[] = [];
  private hazeBase: THREE.Vector3[] = [];

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
    const bricks = brickTextures();
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 7), new THREE.MeshStandardMaterial({ map: bricks.map, bumpMap: bricks.bump, bumpScale: 2.2, roughness: 0.92 }));
    wall.position.set(0, 2.9, -2.3);
    wall.receiveShadow = true;
    this.group.add(wall);

    // neon sign
    this.signMat = new THREE.MeshBasicMaterial({ map: neonTexture(opts.sign ?? 'FUNNIER'), transparent: true, depthWrite: false, toneMapped: false });
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

    // mic stand: fitted to the performer's mouth by StageRuntime (fitMic); default for a 1.7 m body
    this.mic = new MicStand();
    this.mic.fitTo(new THREE.Vector3(0, 1.5, 0.1));
    this.group.add(this.mic.group);

    const metal = new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.9, roughness: 0.3 });
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

    // lights — key (front spot), wall wash, back/rim lights, house
    scene.add(new THREE.HemisphereLight(0x3a3060, 0x100808, 0.45));
    this.spot = new THREE.SpotLight(0xfff0dc, 50, 15, 0.3, 0.5, 1.5);
    this.spot.position.set(0.6, 6.2, 4.6);
    this.spot.target.position.set(0, 1.1, 0);
    this.spot.castShadow = opts.shadows ?? true;
    this.spot.shadow.mapSize.set(1024, 1024);
    this.spot.shadow.bias = -0.0005;
    this.group.add(this.spot, this.spot.target);
    // face key: tight warm spot on the head from front-right, high enough to read as theatrical
    const key = new THREE.SpotLight(0xffd8b0, 5, 7, 0.16, 0.6, 1.2);
    key.position.set(1.1, 2.7, 3.0);
    key.target.position.set(0, 1.45, 0);
    this.group.add(key, key.target);
    const fill = new THREE.DirectionalLight(0xd8e4ff, 0.3);
    fill.position.set(-3, 2.5, 4);
    this.group.add(fill);
    // brick wash: grazing light from above so mortar lines and texture read
    for (const x of [-2.6, 2.6]) {
      const wash = new THREE.SpotLight(0xffa080, 7, 7, 0.7, 0.85, 1.3);
      wash.position.set(x, 6.2, -1.2);
      wash.target.position.set(x * 0.7, 1.8, -2.3);
      this.group.add(wash, wash.target);
    }
    // back light: cool white from upstage-high, separates hair/shoulders from the wall
    const back = new THREE.SpotLight(0xdfe8ff, 30, 7, 0.4, 0.6, 1.4);
    back.position.set(0, 3.9, -1.9);
    back.target.position.set(0, 1.4, 0.2);
    this.group.add(back, back.target);
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

    // visible spot cone (shader falloff) + a second, tighter inner cone
    const beamGeo = new THREE.ConeGeometry(1.15, 6.9, 48, 1, true);
    beamGeo.translate(0, -3.45, 0);
    this.beam = new THREE.Mesh(beamGeo, beamMaterial(0xfff1d6, 0.42));
    this.beam.position.copy(this.spot.position);
    this.beam.lookAt(new THREE.Vector3(0, -0.4, -0.15));
    this.beam.rotateX(-Math.PI / 2);
    this.group.add(this.beam);
    const inner = new THREE.Mesh(new THREE.ConeGeometry(0.6, 6.9, 32, 1, true).translate(0, -3.45, 0), beamMaterial(0xfff6e6, 0.2));
    inner.position.copy(this.beam.position); inner.quaternion.copy(this.beam.quaternion);
    this.group.add(inner);
    // haze: slow-drifting soft sprites inside the beam
    const hz = hazeTexture();
    for (let i = 0; i < 14; i++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: hz, color: 0xfff0dc, transparent: true, opacity: 0.07 + (i % 4) * 0.015, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
      const u = i / 13;
      const p = new THREE.Vector3(0.6 - 0.55 * u + Math.sin(i * 2.1) * 0.5, 5.6 - 4.3 * u, 4.4 - 4.1 * u + Math.cos(i * 1.3) * 0.3);
      sp.position.copy(p);
      sp.scale.setScalar(1.4 + (i % 3) * 0.6);
      this.group.add(sp);
      this.haze.push(sp); this.hazeBase.push(p.clone());
    }

    // footlights
    for (let i = -3; i <= 3; i++) {
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffd28a, toneMapped: false }));
      bulb.position.set(i * 1.1, 0.04, 2.15);
      this.group.add(bulb);
    }

    // audience: raked rows of head-and-shoulders silhouettes; a fresnel rim (stage spill)
    // makes them read as shapes against the dark house in the wide shot.
    const rows = opts.audienceRows ?? 4;
    const seats = opts.audienceSeats ?? 11;
    const shoulders = new THREE.CapsuleGeometry(0.2, 0.28, 4, 12);
    shoulders.scale(1.25, 1, 0.7);
    const headGeo = new THREE.SphereGeometry(0.115, 14, 10);
    headGeo.translate(0, 0.42, 0);
    const geo = mergeGeometries(shoulders, headGeo);
    const am = new THREE.MeshStandardMaterial({ color: 0x050407, roughness: 1 });
    am.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>',
        '#include <emissivemap_fragment>\n  float rimF = pow(1.0 - clamp(abs(dot(normalize(normal), normalize(vViewPosition))), 0.0, 1.0), 2.5);\n  totalEmissiveRadiance += vec3(0.6, 0.38, 0.42) * rimF * 0.2;');
    };
    this.audience = new THREE.InstancedMesh(geo, am, rows * seats);
    let n = 0;
    const m = new THREE.Matrix4();
    for (let r = 0; r < rows; r++) {
      for (let s = 0; s < seats; s++) {
        const x = (s - (seats - 1) / 2) * 0.72 + (r % 2 ? 0.36 : 0) + Math.sin(n * 12.9898) * 0.08;
        const z = 3.0 + r * 0.95;
        const y = -0.1 + r * 0.26;
        const sc = 0.82 + ((n * 7) % 5) * 0.035;
        const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.sin(n * 3.7) * 0.25, Math.sin(n * 5.3) * 0.06));
        m.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(sc, sc, sc));
        this.audience.setMatrixAt(n, m);
        this.audienceBase.push(m.clone());
        n++;
      }
    }
    this.group.add(this.audience);
  }

  /** Fit the mic stand to the performer's mouth (world space). */
  fitMic(mouth: THREE.Vector3): void { this.mic.fitTo(mouth); }

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
    for (let i = 0; i < this.haze.length; i++) {
      const b = this.hazeBase[i];
      this.haze[i].position.set(b.x + Math.sin(wallMs * 0.00011 + i) * 0.25, b.y + Math.sin(wallMs * 0.00007 + i * 2) * 0.15, b.z);
      (this.haze[i].material as THREE.SpriteMaterial).rotation = wallMs * 0.00002 * (i % 2 ? 1 : -1);
    }
    for (const [i, rim] of this.rims.entries()) rim.intensity = 40 + 25 * e * Math.abs(Math.sin(wallMs * 0.006 + i));
  }
}
