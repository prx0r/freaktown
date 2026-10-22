/**
 * Mouth anchor — an Object3D parented to the head bone at the mouth, so the
 * stage can put a mic in front of it (and tests can measure mic↔mouth).
 *
 * Estimated once at rest pose from whatever the rig carries:
 *   eyes (VRM leftEye/rightEye) → eye midpoint, down ~5 cm, forward ~5 cm
 *   head bone only              → head joint, up ~4 cm, forward ~8 cm
 *   no head bone                → bounding box: 91% of height, front face
 * Bodies are normalized to ~1.7 m and face +Z, so world offsets are safe.
 */

import * as THREE from 'three';

export function attachMouthAnchor(root: THREE.Object3D, head: THREE.Object3D | null, eyes: THREE.Object3D[] = []): THREE.Object3D {
  root.updateMatrixWorld(true);
  const anchor = new THREE.Object3D();
  anchor.name = 'mouth-anchor';
  const world = new THREE.Vector3();
  const live = eyes.filter(Boolean);
  if (live.length) {
    const tmp = new THREE.Vector3();
    for (const e of live) world.add(e.getWorldPosition(tmp));
    world.multiplyScalar(1 / live.length).add(new THREE.Vector3(0, -0.052, 0.05));
  } else if (head) {
    head.getWorldPosition(world).add(new THREE.Vector3(0, 0.04, 0.08));
  } else {
    const box = new THREE.Box3().setFromObject(root);
    world.set((box.min.x + box.max.x) / 2, box.min.y + (box.max.y - box.min.y) * 0.91, box.max.z);
  }
  const parent = head ?? root;
  parent.add(anchor);
  anchor.position.copy(parent.worldToLocal(world.clone()));
  // undo inherited scale so the anchor is a clean point
  return anchor;
}
