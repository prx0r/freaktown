import * as THREE from 'three';

/** Scale an avatar so it stands `height` tall with feet on y=0, centred on x/z. */
export function normalizeHeight(root: THREE.Object3D, height = 1.7): number {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const size = new THREE.Vector3();
  box.getSize(size);
  if (!isFinite(size.y) || size.y <= 0) return 1;
  const s = height / size.y;
  root.scale.multiplyScalar(s);
  root.updateMatrixWorld(true);
  const box2 = new THREE.Box3().setFromObject(root);
  const c = new THREE.Vector3();
  box2.getCenter(c);
  root.position.x -= c.x;
  root.position.z -= c.z;
  root.position.y -= box2.min.y;
  return s;
}
