(() => {
  const $ = (id) => document.getElementById(id);
  const audio = $('audio');
  const avatar = $('avatar');
  const transcript = $('transcript');
  const playBtn = $('playBtn');
  const laughBtn = $('laughBtn');
  const clapBtn = $('clapBtn');
  const toast = $('toast');
  const waveform = $('waveform');
  const stageGlow = $('stageGlow');
  const themeSelect = $('themeSelect');

  const EMOTIONS = {
    neutral:  { color: '#0D8EA6', ink: '#ffffff', label: 'neutral' },
    deadpan:  { color: '#0B1B3D', ink: '#ffffff', label: 'deadpan' },
    joy:      { color: '#D48A17', ink: '#11131a', label: 'joy' },
    playful:  { color: '#1DB381', ink: '#071710', label: 'playful' },
    tension:  { color: '#BD1E65', ink: '#ffffff', label: 'tension' },
    surprise: { color: '#0D8EA6', ink: '#ffffff', label: 'surprise' },
    warm:     { color: '#D48A17', ink: '#11131a', label: 'warm' },
  };

  let currentSegments = [];
  let animationFrame = null;
  let laughs = 0;
  let claps = 0;
  let audioCtx = null;
  let analyser = null;
  let source = null;
  let bars = [];

  // ----- Theme system -------------------------------------------------
  const savedTheme = localStorage.getItem('freak-town-theme');
  const bootTheme = window.FREAK_TOWN_DEFAULT_THEME || savedTheme || 'bubble-pop';
  document.documentElement.dataset.theme = bootTheme;
  themeSelect.value = bootTheme;

  themeSelect.addEventListener('change', () => {
    document.documentElement.dataset.theme = themeSelect.value;
    localStorage.setItem('freak-town-theme', themeSelect.value);
  });

  // ----- Bubble semantics --------------------------------------------
  function inferEmotion(text) {
    const t = text.toLowerCase();
    if (/\b(love|funny|laugh|great|best|amazing|loved)\b/.test(t)) return 'joy';
    if (/\b(misery|disappointed|dead|bomb|humiliation|no\.|not\b)\b/.test(t)) return 'deadpan';
    if (/\b(what|why|how|who|really|apparently)\b/.test(t) || /\?$/.test(text.trim())) return 'surprise';
    if (/\b(hell|damn|ass|butt|chaos|interrogation)\b/.test(t)) return 'tension';
    if (/\b(dog|pigeon|roomba|knight|buddy|exactly)\b/.test(t)) return 'playful';
    return 'neutral';
  }

  function splitIntoSegments(text) {
    return (text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text])
      .map(s => s.trim())
      .filter(Boolean);
  }

  function normalizeSegments(data) {
    if (Array.isArray(data.segments) && data.segments.length) {
      return data.segments.map((seg, i) => ({
        id: seg.id ?? i,
        text: seg.text || '',
        emotion: seg.emotion || inferEmotion(seg.text || ''),
        intensity: clamp(Number(seg.intensity ?? 0.65), 0, 1),
        pace: clamp(Number(seg.pace ?? seg.rate ?? 1), 0.65, 1.6),
        pauseAfterMs: Math.max(0, Number(seg.pause_after_ms ?? seg.pauseAfterMs ?? 420)),
        startMs: Number.isFinite(seg.start_ms) ? Number(seg.start_ms) : null,
        endMs: Number.isFinite(seg.end_ms) ? Number(seg.end_ms) : null,
      }));
    }

    return splitIntoSegments(data.text || '').map((text, i) => {
      const words = text.split(/\s+/).length;
      const emphatic = /!$/.test(text);
      const question = /\?$/.test(text);
      const pace = clamp(0.92 + Math.min(words, 22) / 80 + (emphatic ? 0.12 : 0), 0.78, 1.34);
      const pauseAfterMs = question ? 620 : emphatic ? 470 : /\.$/.test(text) ? 520 : 340;
      return {
        id: i,
        text,
        emotion: inferEmotion(text),
        intensity: emphatic ? 0.88 : question ? 0.72 : 0.62,
        pace,
        pauseAfterMs,
        startMs: null,
        endMs: null,
      };
    });
  }

  function buildTiming(segments, durationSec) {
    if (segments.every(s => Number.isFinite(s.startMs) && Number.isFinite(s.endMs))) return segments;

    const totalMs = Math.max(1000, durationSec * 1000);
    const pauseBudget = segments.reduce((sum, s) => sum + s.pauseAfterMs, 0);
    const speakBudget = Math.max(totalMs * 0.55, totalMs - Math.min(pauseBudget, totalMs * 0.35));
    const weights = segments.map(s => Math.max(1, s.text.split(/\s+/).length) / s.pace);
    const totalWeight = weights.reduce((a, b) => a + b, 0);

    let cursor = 0;
    segments.forEach((s, i) => {
      const duration = speakBudget * (weights[i] / totalWeight);
      s.startMs = cursor;
      s.endMs = cursor + duration;
      cursor = s.endMs + s.pauseAfterMs;
    });

    // Normalize if estimates overshoot actual audio.
    if (cursor > totalMs && cursor > 0) {
      const scale = totalMs / cursor;
      segments.forEach(s => {
        s.startMs *= scale;
        s.endMs *= scale;
        s.pauseAfterMs *= scale;
      });
    }
    return segments;
  }

  function renderBubbles(segments) {
    transcript.innerHTML = '';
    segments.forEach((seg, i) => {
      const e = EMOTIONS[seg.emotion] || EMOTIONS.neutral;
      const bubble = document.createElement('article');
      bubble.className = 'speech-bubble';
      bubble.dataset.index = i;
      bubble.dataset.emotion = seg.emotion;
      bubble.style.setProperty('--emotion', e.color);
      bubble.style.setProperty('--bubble-ink', e.ink);
      bubble.style.setProperty('--intensity', seg.intensity);
      bubble.style.setProperty('--pace-width', `${Math.round(300 + (seg.pace - 0.65) * 280)}px`);
      bubble.style.setProperty('--pause-gap', `${Math.round(clamp(seg.pauseAfterMs / 26, 8, 34))}px`);
      bubble.style.setProperty('--tilt', `${((i % 5) - 2) * 0.45}deg`);
      bubble.innerHTML = `
        <div class="bubble-meta">
          <span>${seg.emotion}</span>
          <span>${seg.pace.toFixed(2)}×</span>
        </div>
        <p>${escapeHtml(seg.text)}</p>
        <div class="bubble-tail" aria-hidden="true"></div>`;
      transcript.appendChild(bubble);
    });
  }

  // ----- Audio visualization -----------------------------------------
  for (let i = 0; i < 32; i++) {
    const bar = document.createElement('i');
    waveform.appendChild(bar);
    bars.push(bar);
  }

  function setupAudio() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.78;
    source = audioCtx.createMediaElementSource(audio);
    source.connect(analyser);
    analyser.connect(audioCtx.destination);
  }

  function updateWaveform() {
    if (!analyser || audio.paused) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    bars.forEach((bar, i) => {
      const v = data[(i * 2) % data.length] || 0;
      bar.style.setProperty('--bar', `${Math.max(5, (v / 255) * 34)}px`);
      bar.style.opacity = String(0.35 + (v / 255) * 0.65);
    });
    requestAnimationFrame(updateWaveform);
  }

  // ----- Playback -----------------------------------------------------
  async function playSet() {
    playBtn.disabled = true;
    setPlayLabel('⏳', 'GENERATING');
    $('statusText').textContent = 'GENERATING';

    try {
      const res = await fetch('/api/set');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      $('showNum').textContent = `SHOW #${data.show_number ?? '—'}`;
      $('setTitle').textContent = data.title || 'UNTITLED SET';
      currentSegments = normalizeSegments(data);
      renderBubbles(currentSegments);

      audio.src = data.audio;
      audio.load();
      audio.onloadedmetadata = () => {
        currentSegments = buildTiming(currentSegments, audio.duration || 60);
        renderBubbles(currentSegments);
      };

      audio.oncanplaythrough = async () => {
        setupAudio();
        if (audioCtx?.state === 'suspended') await audioCtx.resume();
        await audio.play();
        playBtn.disabled = false;
        setPlayLabel('⏸', 'PAUSE');
        $('statusText').textContent = 'LIVE';
        avatar.classList.add('speaking');
        laughBtn.disabled = false;
        clapBtn.disabled = false;
        tick();
        updateWaveform();
      };

      audio.onended = finishSet;
    } catch (err) {
      console.error(err);
      playBtn.disabled = false;
      setPlayLabel('▶', 'PLAY SET');
      $('statusText').textContent = 'READY';
      showToast('Could not load the set');
    }
  }

  function finishSet() {
    cancelAnimationFrame(animationFrame);
    avatar.classList.remove('speaking');
    avatar.dataset.emotion = 'neutral';
    setPlayLabel('▶', 'PLAY SET');
    $('statusText').textContent = 'COMPLETE';
    laughBtn.disabled = true;
    clapBtn.disabled = true;
    showToast(`${laughs} laughs · ${claps} claps`);
  }

  function togglePause() {
    if (!audio.src) return playSet();
    if (audio.paused) {
      audio.play();
      avatar.classList.add('speaking');
      setPlayLabel('⏸', 'PAUSE');
      $('statusText').textContent = 'LIVE';
      tick();
      updateWaveform();
    } else {
      audio.pause();
      avatar.classList.remove('speaking');
      setPlayLabel('▶', 'RESUME');
      $('statusText').textContent = 'PAUSED';
      cancelAnimationFrame(animationFrame);
    }
  }

  function tick() {
    cancelAnimationFrame(animationFrame);
    const now = audio.currentTime * 1000;
    const duration = Math.max(0.001, audio.duration || 1);
    $('timeReadout').textContent = formatTime(audio.currentTime);

    let activeIndex = -1;
    currentSegments.forEach((seg, i) => {
      const el = transcript.querySelector(`[data-index="${i}"]`);
      if (!el) return;
      const revealed = now >= seg.startMs;
      const active = now >= seg.startMs && now < seg.endMs;
      el.classList.toggle('revealed', revealed);
      el.classList.toggle('active', active);
      if (active) activeIndex = i;
    });

    if (activeIndex >= 0) {
      const seg = currentSegments[activeIndex];
      const el = transcript.querySelector(`[data-index="${activeIndex}"]`);
      avatar.dataset.emotion = seg.emotion;
      avatar.style.setProperty('--emotion', (EMOTIONS[seg.emotion] || EMOTIONS.neutral).color);
      stageGlow.style.setProperty('--emotion', (EMOTIONS[seg.emotion] || EMOTIONS.neutral).color);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    document.documentElement.style.setProperty('--progress', `${(audio.currentTime / duration) * 100}%`);
    if (!audio.paused && !audio.ended) animationFrame = requestAnimationFrame(tick);
  }

  // ----- Reactions ----------------------------------------------------
  async function react(type) {
    try { await fetch(`/api/${type}`, { method: 'POST' }); } catch (_) {}
    if (type === 'laugh') {
      laughs += 1;
      $('laughCount').textContent = laughs;
      showToast('😂');
    } else {
      claps += 1;
      $('clapCount').textContent = claps;
      showToast('👏');
    }
  }

  // ----- Helpers ------------------------------------------------------
  let toastTimer;
  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 1300);
  }

  function setPlayLabel(icon, text) {
    playBtn.innerHTML = `${icon} <span>${text}</span>`;
  }

  function formatTime(sec) {
    if (!Number.isFinite(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  playBtn.addEventListener('click', () => {
    if (!audio.src || audio.ended) playSet(); else togglePause();
  });
  laughBtn.addEventListener('click', () => react('laugh'));
  clapBtn.addEventListener('click', () => react('clap'));

  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.code === 'Space') { e.preventDefault(); if (!audio.src || audio.ended) playSet(); else togglePause(); }
    if (e.key.toLowerCase() === 'l' && !laughBtn.disabled) react('laugh');
    if (e.key.toLowerCase() === 'k' && !clapBtn.disabled) react('clap');
  });
})();
