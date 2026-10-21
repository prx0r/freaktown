/**
 * CpuDeformer — software skinning + morphs for GPUs that can't do vertex
 * texture fetch (SwiftShader-Vulkan on linux-arm64 loses the WebGL context
 * on three's bone/morph textures). Opt-in (`cpuSkinning`): CI, headless
 * capture, very old devices. Each skinned/morphed mesh is hidden and a
 * plain proxy mesh gets its deformed positions every frame via
 * Mesh.getVertexPosition (three's own CPU path: morphs, then bones).
 */

import * as THREE from 'three';

interface Pair { src: THREE.Mesh; proxy: THREE.Mesh; pos: THREE.BufferAttribute }

export class CpuDeformer {
  private pairs: Pair[] = [];
  private v = new THREE.Vector3();
  private root: THREE.Object3D;

  constructor(root: THREE.Object3D) {
    this.root = root;
    const targets: THREE.Mesh[] = [];
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && ((m as THREE.SkinnedMesh).isSkinnedMesh || m.morphTargetInfluences?.length)) targets.push(m);
    });
    for (const src of targets) {
      const g = new THREE.BufferGeometry();
      for (const [name, attr] of Object.entries(src.geometry.attributes)) {
        if (name === 'skinIndex' || name === 'skinWeight') continue;
        g.setAttribute(name, name === 'position' ? (attr as THREE.BufferAttribute).clone() : attr);
      }
      if (src.geometry.index) g.setIndex(src.geometry.index);
      for (const grp of src.geometry.groups) g.addGroup(grp.start, grp.count, grp.materialIndex);
      const pos = g.getAttribute('position') as THREE.BufferAttribute;
      pos.setUsage(THREE.DynamicDrawUsage);
      const proxy = new THREE.Mesh(g, src.material);
      proxy.name = `${src.name}__cpu`;
      proxy.castShadow = src.castShadow;
      proxy.frustumCulled = false;
      proxy.renderOrder = src.renderOrder;
      src.parent?.add(proxy);
      proxy.position.copy(src.position);
      proxy.quaternion.copy(src.quaternion);
      proxy.scale.copy(src.scale);
      src.visible = false;
      this.pairs.push({ src, proxy, pos });
    }
  }

  get count(): number { return this.pairs.length; }

  update(): void {
    this.root.updateMatrixWorld(true);
    const v = this.v;
    for (const { src, proxy, pos } of this.pairs) {
      proxy.material = src.material;
      const n = pos.count;
      for (let i = 0; i < n; i++) {
        src.getVertexPosition(i, v);
        pos.setXYZ(i, v.x, v.y, v.z);
      }
      pos.needsUpdate = true;
    }
  }
}
