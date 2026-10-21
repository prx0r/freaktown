// Vector tests for affect-servo.js. Deterministic: same inputs, same outputs.
// Run: node test_affect_servo.js (exit 1 on failure).
global.window = undefined;
const fs = require("fs");
const src = fs.readFileSync(__dirname + "/affect-servo.js", "utf8");
new Function(src)();
const S = globalThis.AffectServo;

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log("PASS " + name); }
  else { fail++; console.log("FAIL " + name); }
}
function approx(a, b, tol) { return Math.abs(a - b) <= (tol || 1e-9); }

// determinism: run twice, identical
const d1 = S.affectToDelivery(0.6, 0.2, 0.1);
const d2 = S.affectToDelivery(0.6, 0.2, 0.1);
check("deterministic", JSON.stringify(d1) === JSON.stringify(d2));

// bounds on a grid
let inBounds = true;
for (const a of [-1, -0.5, 0, 0.5, 1])
  for (const v of [-1, 0, 1])
    for (const p of [-1, 0, 1]) {
      const d = S.affectToDelivery(a, v, p);
      if (!(d.energy >= 0 && d.energy <= 1 && d.pace >= 0.6 &&
            d.pauseMs >= 250 && d.emphasis >= 0 && d.emphasis <= 1))
        inBounds = false;
    }
check("bounds hold on grid", inBounds);

// monotonicity: higher arousal → more energy, shorter pauses
const lo = S.affectToDelivery(-0.8, 0, 0);
const hi = S.affectToDelivery(0.8, 0, 0);
check("arousal raises energy", hi.energy > lo.energy);
check("arousal shortens pauses", hi.pauseMs < lo.pauseMs);
check("hot flag fires when hot", hi.hot === true && lo.hot === false);

// smile fusion: blank face ~0, full grin high, monotonic
const blank = S.smileFusion({});
check("blank face ~0", blank < 0.05);
const grin = S.smileFusion({ mouthSmileLeft: 1, mouthSmileRight: 1 });
const full = S.smileFusion({ mouthSmileLeft: 1, mouthSmileRight: 1,
  cheekSquintLeft: 1, cheekSquintRight: 1, jawOpen: 0.5 });
check("grin > blank", grin > blank);
check("more signal > less", full > grin);
check("fusion bounded", full <= 1);

// vote weights: snap 1.25, slow 0.7, mid 1.0
check("snap weight", approx(S.voteWeight(800), 1.25, 0.01));
check("slow weight", approx(S.voteWeight(15000), 0.7, 0.01));
check("mid weight", approx(S.voteWeight(5000), 1.0, 0.01));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
