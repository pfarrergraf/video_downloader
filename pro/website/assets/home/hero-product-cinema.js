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

  // Timings only — each scene carries its own (already-translated)
  // aria-label for screen readers; there's no on-screen caption to sync.
  const sequence = [
    { id: 'source', at: 0, n: '01' },
    { id: 'share', at: 1350, n: '02' },
    { id: 'format', at: 2850, n: '03' },
    { id: 'stream', at: 4300, n: '04' },
    { id: 'inside', at: 6750, n: '05' },
    { id: 'success', at: 9050, n: '06' },
  ];

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
    root.classList.remove('is-running');
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
    timers.push(setTimeout(() => root.classList.remove('is-running'), 10400));
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
    const palette = ['#ff657d', '#ebc978', '#40e3c4'];
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
        const group = i % 3;
        const anchors = [{ x: w * .08, y: h * .23 }, { x: w * .91, y: h * .25 }, { x: w * .88, y: h * .77 }];
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
      const anchors = [{ x: w * .08, y: h * .23 }, { x: w * .91, y: h * .25 }, { x: w * .88, y: h * .77 }];
      const a = anchors[p.c];
      const t = .5 + .5 * Math.sin(time * .00025 + p.p);
      const bends = [{ x: w * .22, y: h * .32 }, { x: w * .78, y: h * .30 }, { x: w * .73, y: h * .69 }];
      return { x: bezier(a.x, bends[p.c].x, center.x * .88, center.x, t * .35), y: bezier(a.y, bends[p.c].y, center.y * .9, center.y, t * .35) };
    }

    function drawIcon(p) {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.strokeStyle = palette[p.c];
      ctx.fillStyle = palette[p.c];
      ctx.lineWidth = 1.2;
      if (p.c === 0) { ctx.beginPath(); ctx.moveTo(-3, -4); ctx.lineTo(4, 0); ctx.lineTo(-3, 4); ctx.closePath(); ctx.fill(); }
      else if (p.c === 1) { for (let x = -4; x <= 4; x += 2) { const hh = 2 + Math.abs(Math.sin((x + p.p) * 1.7)) * 4; ctx.fillRect(x, -hh / 2, 1, hh); } }
      else { ctx.strokeRect(-4, -4, 8, 8); ctx.beginPath(); ctx.moveTo(-3, 2); ctx.lineTo(-1, 0); ctx.lineTo(1, 2); ctx.lineTo(4, -1); ctx.stroke(); }
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
