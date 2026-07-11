(() => {
'use strict';
const root = document.querySelector('[data-pc-root]');
if (!root) return;
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const cinema = root.querySelector('[data-pc-cinema]');
const deviceWrap = root.querySelector('[data-pc-device-wrap]');
const scenes = [...root.querySelectorAll('[data-pc-scene]')];
const replayButtons = [...root.querySelectorAll('[data-pc-replay]')];
const timelineNumber = root.querySelector('[data-pc-timeline-number]');
const timelineCopy = root.querySelector('[data-pc-timeline-copy]');
const timelineProgress = root.querySelector('[data-pc-timeline-progress]');
const steps = [
{ id: 'source', number: '01', copy: 'Medienlink öffnen und teilen.', at: 0 },
{ id: 'share', number: '02', copy: 'DownloadThat im Teilen-Menü auswählen.', at: 1450 },
{ id: 'format', number: '03', copy: 'Video, Audio oder Bilder wählen.', at: 3000 },
{ id: 'transfer', number: '04', copy: 'Die Datei wird direkt lokal verarbeitet.', at: 4550 },
{ id: 'success', number: '05', copy: 'Gespeichert. Direkt auf dem Gerät.', at: 7050 }
];
let timers = [];
let currentStep = 'source';
function clearTimers() {
timers.forEach(window.clearTimeout);
timers = [];
cinema.classList.remove('is-running');
}
function showStep(id) {
currentStep = id;
scenes.forEach((scene) => scene.classList.toggle('is-active', scene.dataset.pcScene === id));
const index = steps.findIndex((step) => step.id === id);
const step = steps[Math.max(index, 0)];
timelineNumber.textContent = step.number;
timelineCopy.textContent = step.copy;
timelineProgress.style.width = `${((index + 1) / steps.length) * 100}%`;
root.dataset.pcStep = id;
if (id === 'transfer' && !prefersReducedMotion) {
timers.push(window.setTimeout(() => showStep('success'), 2420));
}
}
function runSequence() {
clearTimers();
showStep('source');
if (prefersReducedMotion) {
showStep('success');
return;
}
cinema.classList.add('is-running');
steps.forEach((step) => timers.push(window.setTimeout(() => showStep(step.id), step.at)));
timers.push(window.setTimeout(() => cinema.classList.remove('is-running'), 8050));
}
replayButtons.forEach((button) => button.addEventListener('click', runSequence));
root.addEventListener('click', (event) => {
const next = event.target.closest('[data-pc-next]');
if (!next) return;
clearTimers();
showStep(next.dataset.pcNext);
});
if (!prefersReducedMotion) {
cinema.addEventListener('pointermove', (event) => {
const rect = cinema.getBoundingClientRect();
const x = (event.clientX - rect.left) / rect.width - 0.5;
const y = (event.clientY - rect.top) / rect.height - 0.5;
deviceWrap.style.transform = `rotateY(${x * 15}deg) rotateX(${-y * 11}deg) translate3d(${x * 12}px, ${y * 10}px, 0)`;
});
cinema.addEventListener('pointerleave', () => { deviceWrap.style.transform = ''; });
}
function createParticleField() {
const canvas = root.querySelector('[data-pc-particles]');
if (!canvas || prefersReducedMotion) return;
const context = canvas.getContext('2d', { alpha: true });
if (!context) return;
let width = 0;
let height = 0;
let dpr = 1;
let particles = [];
let raf = 0;
let last = performance.now();
const pointer = { x: -9999, y: -9999 };
const arrowTargets = [];
function buildArrowTargets(count) {
arrowTargets.length = 0;
const cx = width * 0.5;
const cy = height * 0.48;
const scale = Math.min(width, height) * 0.16;
const segments = [
[[0, -1], [0, .45]],
[[-.62, -.02], [0, .64]],
[[.62, -.02], [0, .64]],
[[-.48, .9], [.48, .9]]
];
for (let i = 0; i < count; i += 1) {
const segment = segments[i % segments.length];
const t = ((i * 0.61803398875) % 1);
const x = segment[0][0] + (segment[1][0] - segment[0][0]) * t;
const y = segment[0][1] + (segment[1][1] - segment[0][1]) * t;
arrowTargets.push({ x: cx + x * scale, y: cy + y * scale });
}
}
function resize() {
const rect = canvas.getBoundingClientRect();
width = Math.max(1, rect.width);
height = Math.max(1, rect.height);
dpr = Math.min(window.devicePixelRatio || 1, 2);
canvas.width = Math.round(width * dpr);
canvas.height = Math.round(height * dpr);
context.setTransform(dpr, 0, 0, dpr, 0, 0);
const count = Math.min(180, Math.max(90, Math.round(width / 5)));
buildArrowTargets(count);
particles = Array.from({ length: count }, (_, index) => ({
x: Math.random() * width,
y: Math.random() * height,
vx: 0,
vy: 0,
radius: 0.8 + Math.random() * 1.8,
color: index % 3,
phase: Math.random() * Math.PI * 2
}));
}
function targetFor(particle, index, time) {
const step = root.dataset.pcStep || currentStep;
if (step === 'transfer') return arrowTargets[index];
if (step === 'success') {
return {
x: width * 0.5 + Math.cos(index * 2.399) * Math.min(width, height) * 0.025,
y: height * 0.5 + Math.sin(index * 2.399) * Math.min(width, height) * 0.025
};
}
const angle = index * 2.399 + time * 0.00006;
const radius = Math.min(width, height) * (0.22 + (index % 11) * 0.012);
return {
x: width * 0.5 + Math.cos(angle) * radius,
y: height * 0.48 + Math.sin(angle) * radius * 0.62
};
}
function draw(time) {
const delta = Math.min(32, time - last);
last = time;
context.clearRect(0, 0, width, height);
const palette = ['rgba(255,101,125,.82)', 'rgba(235,201,120,.78)', 'rgba(64,227,196,.8)'];
particles.forEach((particle, index) => {
const target = targetFor(particle, index, time);
const attraction = root.dataset.pcStep === 'transfer' ? 0.0068 : 0.0028;
particle.vx += (target.x - particle.x) * attraction * (delta / 16.67);
particle.vy += (target.y - particle.y) * attraction * (delta / 16.67);
const dx = pointer.x - particle.x;
const dy = pointer.y - particle.y;
const distance = Math.hypot(dx, dy);
if (distance < 110) {
const force = (110 - distance) / 110;
particle.vx -= dx / Math.max(distance, 1) * force * 0.13;
particle.vy -= dy / Math.max(distance, 1) * force * 0.13;
}
particle.vx *= 0.91;
particle.vy *= 0.91;
particle.x += particle.vx;
particle.y += particle.vy;
context.beginPath();
context.fillStyle = palette[particle.color];
context.globalAlpha = 0.48 + Math.sin(time * 0.0014 + particle.phase) * 0.22;
context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
context.fill();
});
context.globalAlpha = 1;
raf = requestAnimationFrame(draw);
}
canvas.addEventListener('pointermove', (event) => {
const rect = canvas.getBoundingClientRect();
pointer.x = event.clientX - rect.left;
pointer.y = event.clientY - rect.top;
});
canvas.addEventListener('pointerleave', () => { pointer.x = -9999; pointer.y = -9999; });
document.addEventListener('visibilitychange', () => {
if (document.hidden) cancelAnimationFrame(raf);
else { last = performance.now(); raf = requestAnimationFrame(draw); }
});
window.addEventListener('resize', resize, { passive: true });
resize();
raf = requestAnimationFrame(draw);
}
createParticleField();
window.setTimeout(runSequence, prefersReducedMotion ? 0 : 850);
})();