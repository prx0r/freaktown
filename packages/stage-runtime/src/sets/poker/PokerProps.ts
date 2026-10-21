/**
 * PokerProps — the table's moving parts: hole cards, board, chip stacks, pot,
 * dealer button. Poker contract events call these; everything tweens so the
 * camera sees chips slide and cards fly from the dealer.
 */
import * as THREE from 'three';
import type { CardV1 } from '@freaktown/contracts';
import type { SetDefinition } from '../types';
import { canvasTexture } from '../builders/common';
import { POKER_TOP_Y } from '../builders/sets';

const SUIT: Record<string, { s: string; c: string }> = {
  spades: { s: '♠', c: '#111' }, clubs: { s: '♣', c: '#111' }, hearts: { s: '♥', c: '#d01020' }, diamonds: { s: '♦', c: '#d01020' },
};
const CW = 0.09, CH = 0.126;
const texCache = new Map<string, THREE.Texture>();
function faceTex(c: CardV1): THREE.Texture {
  const k = `${c.rank}${c.suit}`;
  let t = texCache.get(k);
  if (!t) {
    const su = SUIT[c.suit];
    t = canvasTexture(128, 180, (x) => {
      x.fillStyle = '#fbfbf6'; x.fillRect(0, 0, 128, 180);
      x.strokeStyle = '#999'; x.lineWidth = 4; x.strokeRect(2, 2, 124, 176);
      x.fillStyle = su.c; x.font = 'bold 54px Georgia, serif'; x.fillText(c.rank === 'T' ? '10' : c.rank, 10, 56);
      x.font = '84px Georgia, serif'; x.textAlign = 'center'; x.fillText(su.s, 64, 150);
    });
    texCache.set(k, t);
  }
  return t;
}
let backTex: THREE.Texture | null = null;
function back(): THREE.Texture {
  if (!backTex) backTex = canvasTexture(128, 180, (x) => {
    x.fillStyle = '#fbfbf6'; x.fillRect(0, 0, 128, 180); x.fillStyle = '#9c1424'; x.fillRect(8, 8, 112, 164);
    x.strokeStyle = '#f2c94c'; x.lineWidth = 3; for (let i = -180; i < 180; i += 16) { x.beginPath(); x.moveTo(8 + i, 8); x.lineTo(8 + i + 164, 172); x.stroke(); }
  });
  return backTex;
}

function cardMesh(c: CardV1 | null): THREE.Mesh {
  const edge = new THREE.MeshStandardMaterial({ color: 0xf0f0ea });
  const top = c ? new THREE.MeshStandardMaterial({ map: faceTex(c), roughness: 0.5 }) : new THREE.MeshStandardMaterial({ map: back(), roughness: 0.5 });
  const bottom = new THREE.MeshStandardMaterial({ map: back(), roughness: 0.5 });
  const m = new THREE.Mesh(new THREE.BoxGeometry(CW, 0.002, CH), [edge, edge, top, bottom, edge, edge]);
  m.castShadow = true;
  return m;
}

const CHIP_COLORS = [0xd8d8d8, 0xd01f2f, 0x1f5fd0, 0x1b8a3a, 0x111111];
function chipStack(amount: number): THREE.Group {
  const g = new THREE.Group();
  const n = Math.max(1, Math.min(18, Math.round(amount / 10)));
  const geo = new THREE.CylinderGeometry(0.02, 0.02, 0.006, 16);
  for (let i = 0; i < n; i++) {
    const col = CHIP_COLORS[Math.floor(i / 4) % CHIP_COLORS.length];
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: col, roughness: 0.4 }));
    m.position.set(((i % 3) - 1) * 0.004, 0.003 + i * 0.0065, 0);
    g.add(m);
  }
  g.userData.amount = amount;
  return g;
}

interface Tween { obj: THREE.Object3D; from: THREE.Vector3; to: THREE.Vector3; t: number; dur: number; arc: number; done?: () => void }

export class PokerProps {
  readonly group = new THREE.Group();
  private def: SetDefinition;
  private tweens: Tween[] = [];
  private hole = new Map<number, THREE.Mesh[]>();
  private boardCards: THREE.Mesh[] = [];
  private stacks = new Map<number, THREE.Group>();
  private pot: THREE.Group | null = null;
  private button: THREE.Mesh;
  potAmount = 0;
  board: CardV1[] = [];

  constructor(def: SetDefinition) {
    this.def = def;
    const btex = canvasTexture(64, 64, (x) => { x.fillStyle = '#fff'; x.beginPath(); x.arc(32, 32, 31, 0, Math.PI * 2); x.fill(); x.fillStyle = '#111'; x.font = 'bold 40px Arial'; x.textAlign = 'center'; x.fillText('D', 32, 46); });
    this.button = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.01, 24), [new THREE.MeshStandardMaterial({ color: 0xffffff }), new THREE.MeshStandardMaterial({ map: btex }), new THREE.MeshStandardMaterial({ color: 0xffffff })]);
    this.button.position.set(0, POKER_TOP_Y + 0.005, -0.4);
    this.group.add(this.button);
  }

  /** Point on the felt between the centre and seat `i` (k = 0 centre … 1 seat). */
  spot(seat: number, k: number, lateral = 0): THREE.Vector3 {
    const s = this.def.seats[seat];
    if (!s) return new THREE.Vector3(0, POKER_TOP_Y, 0);
    const x = s.position[0] * k, z = s.position[2] * k;
    const sx = Math.cos(s.rotation), sz = -Math.sin(s.rotation);
    return new THREE.Vector3(x + sx * lateral, POKER_TOP_Y + 0.002, z + sz * lateral);
  }
  private dealer(): THREE.Vector3 { return new THREE.Vector3(0, POKER_TOP_Y + 0.05, -0.6); }
  private potSpot(): THREE.Vector3 { return new THREE.Vector3(0, POKER_TOP_Y + 0.002, 0.12); }

  private tween(obj: THREE.Object3D, to: THREE.Vector3, dur = 0.45, arc = 0.08, done?: () => void): void {
    this.tweens = this.tweens.filter((t) => t.obj !== obj);
    this.tweens.push({ obj, from: obj.position.clone(), to: to.clone(), t: 0, dur, arc, done });
  }

  reset(): void {
    for (const cs of this.hole.values()) for (const c of cs) this.group.remove(c);
    for (const c of this.boardCards) this.group.remove(c);
    for (const s of this.stacks.values()) this.group.remove(s);
    if (this.pot) this.group.remove(this.pot);
    this.hole.clear(); this.boardCards = []; this.stacks.clear(); this.pot = null; this.potAmount = 0; this.board = [];
    this.tweens = [];
  }

  setButton(seat: number): void { this.tween(this.button, this.spot(seat, 0.62, -0.18).setY(POKER_TOP_Y + 0.005), 0.5, 0.05); }

  deal(seat: number, cards: CardV1[], faceUp = false): void {
    const prev = this.hole.get(seat);
    if (prev) for (const c of prev) this.group.remove(c);
    const s = this.def.seats[seat];
    const meshes = cards.map((c, i) => {
      const m = cardMesh(faceUp ? c : null);
      m.userData.card = c;
      m.position.copy(this.dealer());
      m.rotation.y = (s?.rotation ?? 0) + (i ? 0.12 : -0.12);
      this.group.add(m);
      this.tween(m, this.spot(seat, 0.6, (i - 0.5) * 0.07).setY(POKER_TOP_Y + 0.004 + i * 0.002), 0.4 + i * 0.12, 0.12);
      return m;
    });
    this.hole.set(seat, meshes);
  }

  reveal(seat: number, cards: CardV1[]): void {
    const prev = this.hole.get(seat) ?? [];
    prev.forEach((m, i) => {
      const c = cards[i]; if (!c) return;
      const mats = m.material as THREE.MeshStandardMaterial[];
      mats[2] = new THREE.MeshStandardMaterial({ map: faceTex(c), roughness: 0.5 });
      m.material = [...mats];
    });
    if (!prev.length) this.deal(seat, cards, true);
  }

  fold(seat: number): void {
    const cs = this.hole.get(seat) ?? [];
    for (const c of cs) this.tween(c, this.dealer().setY(POKER_TOP_Y + 0.004), 0.5, 0.06, () => this.group.remove(c));
    this.hole.delete(seat);
  }

  setBoard(cards: CardV1[]): void {
    for (let i = this.boardCards.length; i < cards.length; i++) {
      const m = cardMesh(cards[i]);
      m.position.copy(this.dealer());
      this.group.add(m);
      this.tween(m, new THREE.Vector3(-0.26 + i * 0.13, POKER_TOP_Y + 0.004, -0.16), 0.45 + (i % 3) * 0.1, 0.1);
      this.boardCards.push(m);
    }
    this.board = [...cards];
  }

  /** Chips slide seat → pot or pot → seat. */
  chips(from: number | 'pot', to: number | 'pot', amount: number): void {
    if (amount <= 0) return;
    const fly = chipStack(amount);
    fly.position.copy(from === 'pot' ? this.potSpot() : this.spot(from, 0.72));
    this.group.add(fly);
    const dest = to === 'pot' ? this.potSpot() : this.spot(to, 0.72);
    if (to === 'pot') this.potAmount += amount; else this.potAmount = Math.max(0, this.potAmount - amount);
    this.tween(fly, dest, 0.6, 0.15, () => {
      this.group.remove(fly);
      if (to === 'pot') this.rebuildPot();
      else { this.rebuildPot(); this.bumpStack(to, amount); }
    });
  }

  private rebuildPot(): void {
    if (this.pot) this.group.remove(this.pot);
    this.pot = null;
    if (this.potAmount > 0) { this.pot = chipStack(this.potAmount); this.pot.position.copy(this.potSpot()); this.group.add(this.pot); }
  }

  private bumpStack(seat: number, amount: number): void {
    const prev = this.stacks.get(seat);
    const total = (prev?.userData.amount ?? 0) + amount;
    if (prev) this.group.remove(prev);
    const st = chipStack(total); st.position.copy(this.spot(seat, 0.8, 0.12)); this.group.add(st); this.stacks.set(seat, st);
  }

  get counts(): { hole: number; board: number; pot: number } {
    let hole = 0; for (const v of this.hole.values()) hole += v.length;
    return { hole, board: this.boardCards.length, pot: this.potAmount };
  }

  update(dt: number): void {
    for (const t of [...this.tweens]) {
      t.t = Math.min(1, t.t + dt / t.dur);
      const e = t.t < 0.5 ? 2 * t.t * t.t : 1 - (-2 * t.t + 2) ** 2 / 2;
      t.obj.position.lerpVectors(t.from, t.to, e);
      t.obj.position.y += Math.sin(Math.PI * t.t) * t.arc;
      if (t.t >= 1) { this.tweens.splice(this.tweens.indexOf(t), 1); t.done?.(); }
    }
  }
}
