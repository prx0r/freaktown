/**
 * Face sources for the smile referee. Every source yields ARKit-named
 * blendshapes (+ a luma reading for the lighting check) on the device.
 *
 *   camera     getUserMedia → MediaPipe FaceLandmarker (blendshapes on, GPU→CPU fallback),
 *              loaded lazily from the jsDelivr CDN + Google model bucket. Video never leaves the page.
 *   recorded   a recorded/synthetic blendshape stream (JSON) played on the wall clock — the
 *              "fake webcam" the e2e test and the simulated-round render use.
 *   synthetic  a scripted smile level over time (no file needed).
 */
import { lumaOf, syntheticFrame, type Blendshapes } from '@funnier/party';

export interface FaceFrame { t: number; bs: Blendshapes | null; luma: number }
export interface FaceSource { kind: 'camera' | 'recorded' | 'synthetic'; sample(nowMs: number): FaceFrame | null; video?: HTMLVideoElement; stop(): void; status: string }

export interface RecordedFeed { fps?: number; frames: Array<{ t: number; bs?: Blendshapes; smile?: number; luma?: number }> }

export function recordedSource(feed: RecordedFeed, t0: number): FaceSource {
  const frames = [...feed.frames].sort((a, b) => a.t - b.t);
  let i = 0;
  return {
    kind: 'recorded', status: `recorded feed · ${frames.length} frames`,
    sample(now) {
      const rel = now - t0;
      while (i + 1 < frames.length && frames[i + 1].t <= rel) i++;
      const f = frames[i];
      if (!f || rel < frames[0].t) return null;
      return { t: now, bs: f.bs ?? syntheticFrame(f.smile ?? 0), luma: f.luma ?? 0.5 };
    },
    stop() {},
  };
}

/** level(relMs) → smile 0..1; optional darkness windows. */
export function syntheticSource(level: (relMs: number) => number, t0: number, luma: (relMs: number) => number = () => 0.5): FaceSource {
  return { kind: 'synthetic', status: 'synthetic feed', sample: (now) => ({ t: now, bs: syntheticFrame(level(now - t0)), luma: luma(now - t0) }), stop() {} };
}

const TASKS_VISION = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
const FACE_MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

interface Landmarker { detectForVideo(v: HTMLVideoElement, ts: number): { faceBlendshapes?: Array<{ categories: Array<{ categoryName: string; score: number }> }> }; close(): void }

export async function cameraSource(onStatus: (s: string) => void): Promise<FaceSource> {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
  const video = document.createElement('video');
  video.muted = true; video.playsInline = true; video.srcObject = stream;
  await video.play();
  const src: FaceSource = { kind: 'camera', video, status: 'camera on · loading face model…', sample: () => null, stop: () => stream.getTracks().forEach((t) => t.stop()) };
  onStatus(src.status);
  const lumaCanvas = document.createElement('canvas');
  lumaCanvas.width = 32; lumaCanvas.height = 24;
  const lctx = lumaCanvas.getContext('2d', { willReadFrequently: true })!;
  let luma = 0.5, lastLuma = 0, lastTs = -1;
  let lm: Landmarker | null = null;
  // the model loads in the background; until then samples carry luma only (no judging without a face)
  void (async () => {
    try {
      const vision = await import(/* @vite-ignore */ `${TASKS_VISION}/vision_bundle.mjs`);
      const fileset = await vision.FilesetResolver.forVisionTasks(`${TASKS_VISION}/wasm`);
      const make = (delegate: 'GPU' | 'CPU') => vision.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: FACE_MODEL, delegate }, runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: true,
      });
      lm = await make('GPU').catch(() => make('CPU'));
      src.status = 'camera on · face model ready (on-device)';
    } catch (e) {
      src.status = `face model failed to load: ${e instanceof Error ? e.message : String(e)}`;
    }
    onStatus(src.status);
  })();
  src.sample = (now) => {
    if (now - lastLuma > 500) { lastLuma = now; lctx.drawImage(video, 0, 0, 32, 24); luma = lumaOf(lctx.getImageData(0, 0, 32, 24).data, 1); }
    if (!lm || video.readyState < 2) return { t: now, bs: null, luma };
    const ts = Math.max(lastTs + 1, Math.round(now));
    lastTs = ts;
    const r = lm.detectForVideo(video, ts);
    const cats = r.faceBlendshapes?.[0]?.categories;
    if (!cats) return { t: now, bs: null, luma };
    const bs: Blendshapes = {};
    for (const c of cats) bs[c.categoryName] = c.score;
    return { t: now, bs, luma };
  };
  const stop = src.stop;
  src.stop = () => { stop(); lm?.close(); };
  return src;
}
