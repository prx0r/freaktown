/* Smile referee — per-room micro-classifier, trained live in the browser.
 *
 * Privacy: frames never leave the device. Samples live in memory;
 * saved models stay in localStorage (per room) unless the room opts out.
 * No server calls, no uploads, ever.
 *
 * Requires TensorFlow.js on the page before this file:
 *   <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest"></script>
 *   <script src="/static/smile-referee.js"></script>
 *
 * Flow: referee = await SmileReferee.calibrate(video, {samples: 30});
 *   → room shows faces for 30s (smile + neutral prompts)
 *   → referee.predict(canvas) -> smileProb in [0,1]
 * Upgrade path: move fit() into a Web Worker; swap dense net for a
 * MobileNet transfer head when accuracy matters.
 */
(function (global) {
  "use strict";

  const SIZE = 48; // downscaled grayscale working resolution

  function frameToTensor(canvas) {
    // Draw centered square crop, grayscale, normalized to [0,1].
    const c = document.createElement("canvas");
    c.width = SIZE; c.height = SIZE;
    const g = c.getContext("2d", { willReadFrequently: true });
    const s = Math.min(canvas.width, canvas.height);
    g.drawImage(canvas,
      (canvas.width - s) / 2, (canvas.height - s) / 2, s, s, 0, 0, SIZE, SIZE);
    const d = g.getImageData(0, 0, SIZE, SIZE).data;
    const gray = new Float32Array(SIZE * SIZE);
    for (let i = 0; i < SIZE * SIZE; i++) {
      gray[i] = (d[i * 4] * 0.299 + d[i * 4 + 1] * 0.587 + d[i * 4 + 2] * 0.114) / 255;
    }
    return tf.tensor2d(gray, [1, SIZE * SIZE]);
  }

  function buildModel() {
    const m = tf.sequential();
    m.add(tf.layers.dense({ inputShape: [SIZE * SIZE], units: 64, activation: "relu" }));
    m.add(tf.layers.dense({ units: 1, activation: "sigmoid" }));
    m.compile({ optimizer: tf.train.adam(0.01), loss: "binaryCrossentropy", metrics: ["acc"] });
    return m;
  }

  async function calibrate(video, opts) {
    opts = opts || {};
    const n = opts.samples || 30;
    const onStep = opts.onStep || function () {};
    const room = opts.room || "default";
    const model = buildModel();
    const xs = [], ys = [];
    const cap = document.createElement("canvas");
    // Alternate prompts: half neutral, half smile. Caller mirrors the
    // prompt on screen ("show your neutral face…" / "biggest grin…").
    for (let i = 0; i < n; i++) {
      const smiling = i % 2 === 1;
      onStep({ i: i + 1, of: n, smiling: smiling });
      // Prompt must be visible BEFORE capture; otherwise labels are wrong.
      await new Promise(function(resolve){ setTimeout(resolve,
        opts.captureDelayMs == null ? 450 : opts.captureDelayMs); });
      await tf.nextFrame();
      cap.width = video.videoWidth; cap.height = video.videoHeight;
      cap.getContext("2d").drawImage(video, 0, 0);
      xs.push(frameToTensor(cap));
      ys.push(smiling ? 1 : 0);
    }
    const X = tf.concat(xs);
    const Y = tf.tensor2d(ys, [ys.length, 1]);
    xs.forEach(function (t) { t.dispose(); });
    await model.fit(X, Y, {
      epochs: opts.epochs || 25, batchSize: 8, shuffle: true, verbose: 0,
      callbacks: { onEpochEnd: function (e, logs) { onStep({ epoch: e, loss: logs.loss }); } },
    });
    X.dispose(); Y.dispose();
    if (!opts.ephemeral) {
      try { await model.save("localstorage://smile-referee-" + room); } catch (e) { /* private mode */ }
    }
    return makeReferee(model);
  }

  function makeReferee(model) {
    return {
      model: model,
      predict: function (canvas) {
        return tf.tidy(function () {
          return model.predict(frameToTensor(canvas)).dataSync()[0];
        });
      },
      dispose: function () { model.dispose(); },
    };
  }

  async function load(room) {
    try {
      const model = await tf.loadLayersModel("localstorage://smile-referee-" + (room || "default"));
      return makeReferee(model);
    } catch (e) {
      return null;
    }
  }

  global.SmileReferee = { calibrate: calibrate, load: load, SIZE: SIZE };
})(typeof window !== "undefined" ? window : this);
