(() => {
  'use strict';
  const root = document.querySelector('[data-pc3-root]');
  if (!root) return;

  const navEl = document.querySelector('header.nav');
  function syncNavHeight() {
    if (navEl) document.documentElement.style.setProperty('--dt-nav-h', navEl.offsetHeight + 'px');
  }
  syncNavHeight();
  addEventListener('resize', syncNavHeight, { passive: true });
  addEventListener('orientationchange', syncNavHeight);

  const reducedBySystem = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let reduced = reducedBySystem;
  let timers = [];
  let stepIndex = 0;
  const stage = root.querySelector('[data-pc3-stage]');
  const rig = root.querySelector('[data-pc3-camera-rig]');
  const views = [...root.querySelectorAll('[data-pc3-view]')];
  const number = root.querySelector('[data-pc3-index]');
  const progress = root.querySelector('[data-pc3-progress]');
  const motionButton = root.querySelector('[data-pc3-motion]');
  const soundButton = root.querySelector('[data-pc3-sound]');

  // ---- Sound effects (synthesized with the Web Audio API - no audio files,
  // keeping this component's no-external-asset rule). Off by default: an
  // autoplaying hero animation making noise without the visitor asking for
  // it would be intrusive, and browsers block un-gestured audio anyway. The
  // AudioContext is only ever created/resumed from inside the sound
  // toggle's own click handler (a real user gesture) - every later
  // setTimeout-scheduled sound just reuses that already-unlocked context.
  let soundOn = false;
  let audioCtx = null;
  function ensureAudioCtx() {
    if (audioCtx) return audioCtx;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    audioCtx = Ctx ? new Ctx() : null;
    return audioCtx;
  }
  function playClick() {
    if (!soundOn || !audioCtx) return;
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1150, now);
    osc.frequency.exponentialRampToValueAtTime(650, now + 0.05);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.22, now + 0.006);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.07);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(now);
    osc.stop(now + 0.08);
  }
  function playSwipe() {
    if (!soundOn || !audioCtx) return;
    const now = audioCtx.currentTime;
    const duration = 0.3;
    const buffer = audioCtx.createBuffer(1, Math.floor(audioCtx.sampleRate * duration), audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    const noise = audioCtx.createBufferSource();
    noise.buffer = buffer;
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.Q.value = 0.9;
    filter.frequency.setValueAtTime(2600, now);
    filter.frequency.exponentialRampToValueAtTime(500, now + duration);
    const gain = audioCtx.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.24, now + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    noise.connect(filter).connect(gain).connect(audioCtx.destination);
    noise.start(now);
    noise.stop(now + duration);
  }
  // A projector/beamer-like whirr for the download beat: a low motor hum
  // plus a steady run of reel-advance ticks, roughly matching the
  // pc3-progress bar's own 2.05s runtime.
  function playDownloadWhirr() {
    if (!soundOn || !audioCtx) return;
    const now = audioCtx.currentTime;
    const duration = 2.0;
    const hum = audioCtx.createOscillator();
    hum.type = 'sawtooth';
    hum.frequency.value = 96;
    const humFilter = audioCtx.createBiquadFilter();
    humFilter.type = 'lowpass';
    humFilter.frequency.value = 420;
    const humGain = audioCtx.createGain();
    humGain.gain.setValueAtTime(0.0001, now);
    humGain.gain.exponentialRampToValueAtTime(0.05, now + 0.15);
    humGain.gain.setValueAtTime(0.05, now + duration - 0.2);
    humGain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    hum.connect(humFilter).connect(humGain).connect(audioCtx.destination);
    hum.start(now);
    hum.stop(now + duration + 0.05);
    const tickCount = Math.floor(duration / 0.11);
    for (let i = 0; i < tickCount; i++) {
      const t = now + i * 0.11;
      const osc = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      osc.type = 'square';
      osc.frequency.value = 260 + (i % 3) * 12;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.05, t + 0.004);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.03);
      osc.connect(g).connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.04);
    }
  }
  const SOUND_FX = { click: playClick, swipe: playSwipe };

  // Timings only — each scene carries its own (already-translated)
  // aria-label for screen readers; there's no on-screen caption to sync.
  // 'source' and 'share' are now themselves short multi-beat stories (see
  // SOURCE_SUB/SHARE_SUB below); their `at` gaps here leave enough room for
  // those beats to play out before the next main scene cross-fades in.
  const sequence = [
    { id: 'source', at: 0, n: '01' },
    { id: 'share', at: 2700, n: '02' },
    { id: 'format', at: 7400, n: '03' },
    { id: 'stream', at: 9100, n: '04' },
    { id: 'inside', at: 11550, n: '05' },
    { id: 'success', at: 13850, n: '06' },
  ];
  const RUN_DURATION = 15400;

  // Sub-beats for the 'source' scene: the video card is shown, its share CTA
  // grows and re-centers, then the finger cursor taps it. Offsets are
  // relative to whenever show('source') itself runs (autoplay or a manual
  // jump), not the timeline above, so this plays the same whether entered on
  // schedule or via stepthrough.
  // `moves`: where the finger cursor should sit once this beat is showing,
  // as CSS selectors resolved (and measured) at the moment each fires - see
  // moveFingerTo(). By the time 'tap' runs, the CTA's own .5s grow/center
  // transition (from 'highlight') has long finished, so measuring its
  // resting position then is accurate with no extra delay.
  const SOURCE_SUB = [
    { value: 'idle', at: 0 },
    { value: 'highlight', at: 1000 },
    { value: 'tap', at: 1900, moves: [{ delay: 0, target: '.pc3-share--cta' }], sounds: [{ delay: 0, type: 'click' }] },
  ];
  // Sub-beats for the 'share' scene: sheet 1 (no DownloadThat) -> finger
  // swipes to "More" -> tap "More" -> sheet 2 (full app grid) -> finger
  // swipes down to reveal the highlighted DownloadThat tile -> tap.
  // swipe-dt gets two moves: an immediate one to the (stationary) grid's own
  // top edge, so the finger visibly swipes down as
  // .pc3-share-grid__inner's .6s reveal transition runs, then a delayed one
  // (matching that .6s) to the DownloadThat tile's now-settled position.
  // 'more-tap' is a distinct beat from 'swipe-more' (rather than tapping the
  // instant the finger arrives) purely so the tap ripple/click sound fires
  // once the glide has actually finished, not at the start of it.
  const SHARE_SUB = [
    { value: 'sheet1', at: 0 },
    { value: 'swipe-more', at: 1200, moves: [{ delay: 0, target: '.pc3-share-apps__more' }], sounds: [{ delay: 0, type: 'swipe' }] },
    { value: 'more-tap', at: 1700, sounds: [{ delay: 0, type: 'click' }] },
    { value: 'sheet2', at: 2100 },
    { value: 'swipe-dt', at: 3000, moves: [
      { delay: 0, target: '.pc3-share-grid' },
      { delay: 650, target: '.pc3-share-grid__dt' },
    ], sounds: [{ delay: 0, type: 'swipe' }] },
    { value: 'tap', at: 4000, sounds: [{ delay: 0, type: 'click' }] },
  ];

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
    root.classList.remove('is-running');
  }

  // Positions the finger cursor exactly on `target`'s center, measured live
  // (getBoundingClientRect) rather than a percentage guessed against one
  // viewport - keeps it accurate on every real phone/breakpoint, including
  // after CSS transforms (highlight scale, grid reveal) have applied.
  function moveFingerTo(finger, target) {
    if (!finger || !target) return;
    const parent = finger.offsetParent;
    if (!parent) return;
    const parentBox = parent.getBoundingClientRect();
    const targetBox = target.getBoundingClientRect();
    finger.style.left = `${targetBox.left + targetBox.width / 2 - parentBox.left}px`;
    finger.style.top = `${targetBox.top + targetBox.height / 2 - parentBox.top}px`;
  }

  function runSub(viewId, steps) {
    const view = views.find((v) => v.dataset.pc3View === viewId);
    if (!view) return;
    const finger = view.querySelector('.pc3-finger');
    steps.forEach((s) => {
      timers.push(setTimeout(() => { view.dataset.pc3Sub = s.value; }, s.at));
      (s.moves || []).forEach((m) => {
        timers.push(setTimeout(() => moveFingerTo(finger, view.querySelector(m.target)), s.at + m.delay));
      });
      (s.sounds || []).forEach((snd) => {
        const fx = SOUND_FX[snd.type];
        if (fx) timers.push(setTimeout(fx, s.at + snd.delay));
      });
    });
  }

  // Ticks the 'inside' scene's live percentage counter alongside the
  // existing pc3-progress bar's own 2.05s CSS animation (kept in sync by
  // literally sharing that duration) instead of a second CSS-only mechanism,
  // since counting up needs text content, not just a width.
  function runPercent() {
    const el = root.querySelector('[data-pc3-percent]');
    if (!el) return;
    const duration = 2050;
    const start = performance.now();
    function tick(now) {
      const pct = Math.min(100, Math.round(((now - start) / duration) * 100));
      el.textContent = `${pct}%`;
      if (pct < 100 && root.dataset.pc3Phase === 'inside') requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function show(id) {
    const idx = Math.max(0, sequence.findIndex((s) => s.id === id));
    stepIndex = idx;
    root.dataset.pc3Phase = id;
    views.forEach((v) => {
      const active = v.dataset.pc3View === id;
      v.classList.toggle('is-active', active);
      // Inactive scenes must drop out of the accessibility tree and tab
      // order entirely, not just be visually hidden by opacity/transform.
      v.toggleAttribute('aria-hidden', !active);
      v.inert = !active;
    });
    if (id === 'source') runSub('source', SOURCE_SUB);
    if (id === 'share') runSub('share', SHARE_SUB);
    if (id === 'inside') { runPercent(); playDownloadWhirr(); }
    if (number) number.textContent = sequence[idx].n;
    if (progress) progress.style.width = `${((idx + 1) / sequence.length) * 100}%`;
  }

  function play() {
    clearTimers();
    root.classList.add('is-running');
    if (reduced) {
      show('success');
      return;
    }
    sequence.forEach((s) => timers.push(setTimeout(() => show(s.id), s.at)));
    timers.push(setTimeout(() => root.classList.remove('is-running'), RUN_DURATION));
  }

  function nextStep() {
    clearTimers();
    stepIndex = (stepIndex + 1) % sequence.length;
    show(sequence[stepIndex].id);
  }

  root.addEventListener('click', (e) => {
    const next = e.target.closest('[data-pc3-next]');
    if (next) {
      clearTimers();
      show(next.dataset.pc3Next);
      return;
    }
    if (e.target.closest('[data-pc3-replay]')) {
      play();
      return;
    }
    if (e.target.closest('[data-pc3-stepthrough]')) {
      nextStep();
    }
  });

  if (motionButton) {
    motionButton.addEventListener('click', () => {
      reduced = !reduced;
      motionButton.setAttribute('aria-pressed', String(reduced));
      root.classList.toggle('is-reduced', reduced);
      clearTimers();
      show(reduced ? 'success' : 'source');
    });
  }

  if (soundButton) {
    soundButton.addEventListener('click', () => {
      soundOn = !soundOn;
      soundButton.setAttribute('aria-pressed', String(soundOn));
      soundButton.textContent = soundOn ? '🔊' : '🔇';
      if (soundOn) {
        const ctx = ensureAudioCtx();
        if (ctx && ctx.state === 'suspended') ctx.resume();
      }
    });
  }

  if (!reducedBySystem && stage && rig) {
    stage.addEventListener('pointermove', (e) => {
      if (['inside', 'stream'].includes(root.dataset.pc3Phase)) return;
      const r = stage.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - .5;
      const y = (e.clientY - r.top) / r.height - .5;
      rig.style.rotate = `${-y * 2}deg ${x * 2}deg 0deg`;
    });
    stage.addEventListener('pointerleave', () => { rig.style.rotate = ''; });
  }

  // Autoplay timers keep no useful purpose in a hidden tab; the canvas rAF
  // loop below already stops itself, this stops the phase sequence too so
  // a backgrounded tab doesn't silently race through the whole story.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimers();
  });

  function initStream() {
    const canvas = root.querySelector('[data-pc3-stream]');
    const ctx = canvas && canvas.getContext('2d', { alpha: true });
    if (!ctx || reducedBySystem) return;
    let w = 0, h = 0, last = performance.now();
    let raf = 0;
    let slowFrames = 0;
    let capped = false;
    const pointer = { x: -9999, y: -9999 };
    // Two groups (video, audio) — the app's share flow only ever offers
    // Video/Audio (no Images toggle anywhere in the real app), so a third
    // particle group would fly in from an anchor with no matching source
    // card on screen.
    const palette = ['#ff657d', '#ebc978'];
    const particles = [];

    function arrowPoints(count) {
      const pts = [];
      const cx = w * .5, cy = h * .49, s = Math.min(w, h) * .155;
      const segs = [[[0, -1], [0, .38]], [[-.6, -.04], [0, .64]], [[.6, -.04], [0, .64]], [[-.48, .9], [.48, .9]]];
      for (let i = 0; i < count; i++) {
        const seg = segs[i % segs.length], t = (i * .61803398875) % 1;
        pts.push({ x: cx + (seg[0][0] + (seg[1][0] - seg[0][0]) * t) * s, y: cy + (seg[0][1] + (seg[1][1] - seg[0][1]) * t) * s });
      }
      return pts;
    }
    let arrow = [];

    function resize() {
      const r = canvas.getBoundingClientRect();
      w = Math.max(1, r.width);
      h = Math.max(1, r.height);
      const dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(240, Math.max(120, Math.round(w / 4.2)));
      arrow = arrowPoints(count);
      particles.length = 0;
      for (let i = 0; i < count; i++) {
        const group = i % 2;
        const anchors = [{ x: w * .08, y: h * .23 }, { x: w * .91, y: h * .25 }];
        const a = anchors[group];
        particles.push({ x: a.x + (Math.random() - .5) * 50, y: a.y + (Math.random() - .5) * 50, vx: 0, vy: 0, r: .8 + Math.random() * 1.8, c: group, p: i * .77, trail: [] });
      }
      capped = false;
      slowFrames = 0;
    }

    function bezier(a, b, c, d, t) { const mt = 1 - t; return mt * mt * mt * a + 3 * mt * mt * t * b + 3 * mt * t * t * c + t * t * t * d; }

    function target(p, i, time) {
      const phase = root.dataset.pc3Phase;
      const center = { x: w * .5, y: h * .49 };
      if (phase === 'stream') return arrow[i] || center;
      if (phase === 'inside') return center;
      if (phase === 'success') return { x: center.x + Math.cos(i * 2.399) * 20, y: center.y + Math.sin(i * 2.399) * 20 };
      const anchors = [{ x: w * .08, y: h * .23 }, { x: w * .91, y: h * .25 }];
      const a = anchors[p.c];
      const t = .5 + .5 * Math.sin(time * .00025 + p.p);
      const bends = [{ x: w * .22, y: h * .32 }, { x: w * .78, y: h * .30 }];
      return { x: bezier(a.x, bends[p.c].x, center.x * .88, center.x, t * .35), y: bezier(a.y, bends[p.c].y, center.y * .9, center.y, t * .35) };
    }

    function drawIcon(p) {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.strokeStyle = palette[p.c];
      ctx.fillStyle = palette[p.c];
      ctx.lineWidth = 1.2;
      if (p.c === 0) { ctx.beginPath(); ctx.moveTo(-3, -4); ctx.lineTo(4, 0); ctx.lineTo(-3, 4); ctx.closePath(); ctx.fill(); }
      else { for (let x = -4; x <= 4; x += 2) { const hh = 2 + Math.abs(Math.sin((x + p.p) * 1.7)) * 4; ctx.fillRect(x, -hh / 2, 1, hh); } }
      ctx.restore();
    }

    function frame(time) {
      const dt = Math.min(32, time - last);
      last = time;
      ctx.clearRect(0, 0, w, h);
      const phase = root.dataset.pc3Phase;
      particles.forEach((p, i) => {
        const t = target(p, i, time);
        const strength = phase === 'stream' ? .015 : phase === 'inside' ? .027 : .0045;
        p.vx += (t.x - p.x) * strength * (dt / 16.67);
        p.vy += (t.y - p.y) * strength * (dt / 16.67);
        const dx = pointer.x - p.x, dy = pointer.y - p.y, dist = Math.hypot(dx, dy);
        if (dist < 105 && phase !== 'inside') {
          const f = (105 - dist) / 105;
          p.vx -= dx / Math.max(dist, 1) * f * .1;
          p.vy -= dy / Math.max(dist, 1) * f * .1;
        }
        p.vx *= .89; p.vy *= .89; p.x += p.vx; p.y += p.vy;
        p.trail.push({ x: p.x, y: p.y });
        if (p.trail.length > 6) p.trail.shift();
        ctx.beginPath();
        p.trail.forEach((q, j) => { if (j === 0) ctx.moveTo(q.x, q.y); else ctx.lineTo(q.x, q.y); });
        ctx.strokeStyle = palette[p.c] + Math.round(22 + p.trail.length * 4).toString(16).padStart(2, '0');
        ctx.lineWidth = .7;
        ctx.stroke();
        ctx.globalAlpha = phase === 'inside' ? Math.max(0, .75 - Math.hypot(p.x - w * .5, p.y - h * .49) / 150) : .7;
        drawIcon(p);
        ctx.globalAlpha = 1;
      });
      // Sustained sub-25fps frame time on a weak device: drop a third of the
      // particles once rather than keep fighting for a frame budget we don't have.
      if (!capped) {
        slowFrames = dt > 40 ? slowFrames + 1 : 0;
        if (slowFrames > 90) {
          particles.splice(0, Math.floor(particles.length / 3));
          capped = true;
        }
      }
      raf = requestAnimationFrame(frame);
    }

    canvas.addEventListener('pointermove', (e) => { const r = canvas.getBoundingClientRect(); pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top; });
    canvas.addEventListener('pointerleave', () => { pointer.x = -9999; pointer.y = -9999; });
    addEventListener('resize', resize, { passive: true });
    addEventListener('orientationchange', resize);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else { last = performance.now(); raf = requestAnimationFrame(frame); }
    });
    resize();
    raf = requestAnimationFrame(frame);
  }

  initStream();
  show(reduced ? 'success' : 'source');
  setTimeout(play, reduced ? 0 : 850);
})();
