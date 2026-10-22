import { describe, expect, it } from 'vitest';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { createIdentity, getPartyIdentity, listPartyIdentities } from '../src/identity';
import { identityGlb, readGlbJson } from '../src/glb';
import { TntsGame } from '../src/game';

describe('agent-made identity → procedural GLB → registry', () => {
  it('Hark Lantern is registered and persists across rooms', () => {
    const h = getPartyIdentity('agent.hark-lantern');
    expect(h).toMatchObject({ name: 'Hark Lantern', origin: 'agent-made', created_by: 'hark' });
    expect(h!.look.avatar_url).toBe('identities/agent.hark-lantern.glb');
    expect(listPartyIdentities().some((x) => x.id === 'agent.hark-lantern')).toBe(true);
    const g = new TntsGame({ agents: ['agent.hark-lantern', 'pog.doug-deadline'] });
    g.seat([{ id: 'you', name: 'You' }]);
    expect((g.cues[0].payload.cast as Array<{ name: string }>)[0].name).toBe('Hark Lantern');
  });

  it('GLB is valid glTF 2.0 with ARKit morphs and loads in three.js', async () => {
    for (const head of ['sphere', 'box', 'lantern', 'blob'] as const) {
      const idn = createIdentity({ by: 't', seed: head, head });
      const glb = identityGlb(idn);
      const { version, length, json } = readGlbJson(glb);
      expect(version).toBe(2);
      expect(length).toBe(glb.length);
      expect(json.meshes.find((m: { name: string }) => m.name === 'face').extras.targetNames).toEqual(['jawOpen', 'mouthSmileLeft', 'mouthSmileRight', 'eyeBlinkLeft', 'eyeBlinkRight']);
      const gltf = await new Promise<any>((res, rej) => new GLTFLoader().parse(glb.buffer.slice(glb.byteOffset, glb.byteOffset + glb.byteLength) as ArrayBuffer, '', res, rej));
      let morphs = 0;
      gltf.scene.traverse((o: any) => { if (o.morphTargetDictionary) morphs += Object.keys(o.morphTargetDictionary).length; });
      expect(morphs).toBe(5);
    }
  });
});
