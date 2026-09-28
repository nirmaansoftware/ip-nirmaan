/*
  hero.js: the homepage hero's construction grid.

  The Nirmaan pixel-N assembles from falling blocks, bottom row first (the
  way a structure goes up), on the same grid the page is drawn on. After it
  settles, cells under the pointer light up in blueprint blue and the odd
  block of the N blinks, as if the building were still being worked on.

  Layout is owned by CSS: the N is drawn inside [data-hero-slot], snapped to
  the grid whose cell size is the hero's --cell custom property. This script
  only reads those boxes.

  Performance: the grid is drawn once to an offscreen canvas; animation
  frames stop entirely when nothing is moving; the whole thing pauses when
  the hero is off-screen or the tab is hidden. With reduced motion, the
  finished mark is drawn once and nothing animates.

  On touch screens there's no pointer to follow, so a tap sends a ripple of
  blue cells out across the grid from where the finger landed.
*/
(function () {
  'use strict';

  var hero = document.querySelector('[data-hero]');
  var canvas = hero && hero.querySelector('[data-hero-canvas]');
  var slot = hero && hero.querySelector('[data-hero-slot]');
  if (!canvas || !slot || !canvas.getContext) return;

  var ctx = canvas.getContext('2d');
  var gridLayer = document.createElement('canvas');
  var gctx = gridLayer.getContext('2d');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  var LOGO = ['10001', '11001', '10101', '10011', '10001'];
  var FALL_MS = 720;
  var ROW_STAGGER_MS = 85;
  var TRAIL_MS = 650;
  var BLINK_MS = 1100;

  var W = 0, H = 0, dpr = 1, cell = 24;
  var blocks = [];          // sub-blocks that make up the N
  var trail = new Map();    // "col,row" -> timestamp lit
  var blink = null;         // { block, t }
  var colors = { grid: '', ink: '', blue: '' };
  var startedAt = 0;
  var settled = false;
  var onScreen = true;
  var rafId = 0;
  var blinkTimer = 0;
  var pointer = null;

  function readColors() {
    var cs = getComputedStyle(document.documentElement);
    colors.grid = cs.getPropertyValue('--grid').trim();
    colors.ink = cs.getPropertyValue('--ink').trim();
    colors.blue = cs.getPropertyValue('--blue').trim();
  }

  function snap(v) { return Math.round(v / cell) * cell; }

  // Resolves a CSS length from a custom property ("1.5rem" or "24px") to px.
  function toPx(value) {
    var n = parseFloat(value);
    if (!isFinite(n)) return 0;
    if (/rem\s*$/.test(value)) return n * parseFloat(getComputedStyle(document.documentElement).fontSize);
    return n;
  }

  function drawGridLayer() {
    gridLayer.width = canvas.width;
    gridLayer.height = canvas.height;
    gctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    gctx.clearRect(0, 0, W, H);
    gctx.strokeStyle = colors.grid;
    gctx.lineWidth = 1;
    gctx.beginPath();
    for (var x = 0.5; x <= W; x += cell) { gctx.moveTo(x, 0); gctx.lineTo(x, H); }
    for (var y = 0.5; y <= H; y += cell) { gctx.moveTo(0, y); gctx.lineTo(W, y); }
    gctx.stroke();
  }

  function layout() {
    var box = hero.getBoundingClientRect();
    var s = slot.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = box.width;
    H = box.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    cell = toPx(getComputedStyle(hero).getPropertyValue('--cell')) || 24;

    // Each logo pixel becomes sub x sub grid cells: as large as the slot allows.
    var sub = Math.max(1, Math.floor(Math.min(s.width, s.height) / (5 * cell)));
    var size = sub * 5 * cell;
    var slotLeft = s.left - box.left, slotTop = s.top - box.top;
    // --mark-align (start | end) is set per breakpoint in styles.css.
    var alignEnd = getComputedStyle(slot).getPropertyValue('--mark-align').trim() === 'end';
    // Snap inward so the mark never pokes past the slot edge it aligns to.
    var ox = alignEnd
      ? Math.floor((slotLeft + s.width - size) / cell) * cell
      : Math.ceil(slotLeft / cell) * cell;
    var oy = snap(slotTop + (s.height - size) / 2);

    var rows = 5 * sub;
    var keepProgress = blocks.length > 0;
    blocks = [];
    LOGO.forEach(function (bits, ly) {
      for (var lx = 0; lx < 5; lx++) {
        if (bits[lx] !== '1') continue;
        for (var sy = 0; sy < sub; sy++) {
          for (var sx = 0; sx < sub; sx++) {
            var gy = ly * sub + sy;
            blocks.push({
              x: ox + (lx * sub + sx) * cell,
              y: oy + gy * cell,
              // bottom rows land first; slight jitter so it reads as hand-placed
              delay: (rows - 1 - gy) * ROW_STAGGER_MS + ((lx * 37 + sx * 53 + sy * 19) % 7) * 18,
              from: -cell * (2 + ((lx + sx + sy) % 4)),
            });
          }
        }
      }
    });
    if (!keepProgress) startedAt = performance.now();
    drawGridLayer();
  }

  function easeOut(t) { return 1 - Math.pow(1 - t, 4); }

  function draw(now) {
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(gridLayer, 0, 0, W, H);

    var busy = false;

    // Pointer trail
    if (trail.size) {
      ctx.fillStyle = colors.blue;
      trail.forEach(function (t, key) {
        if (t > now) return; // a ripple ring that hasn't arrived yet
        var a = 1 - (now - t) / TRAIL_MS;
        if (a <= 0) { trail.delete(key); return; }
        var ij = key.split(',');
        ctx.globalAlpha = a * 0.28;
        ctx.fillRect(+ij[0] * cell + 1, +ij[1] * cell + 1, cell - 1, cell - 1);
      });
      ctx.globalAlpha = 1;
      busy = true;
    }

    // The N
    var elapsed = now - startedAt;
    var allDown = true;
    ctx.fillStyle = colors.ink;
    for (var i = 0; i < blocks.length; i++) {
      var b = blocks[i];
      var p = reduceMotion.matches || settled ? 1 : Math.min(1, Math.max(0, (elapsed - b.delay) / FALL_MS));
      if (p < 1) allDown = false;
      if (p <= 0) continue;
      var y = b.from + (b.y - b.from) * easeOut(p);
      ctx.fillRect(b.x, y, cell, cell);
    }
    if (!allDown) busy = true;
    else if (!settled) { settled = true; scheduleBlink(); }

    // One block of the N blinks blue now and then
    if (blink) {
      var k = (now - blink.t) / BLINK_MS;
      if (k >= 1) blink = null;
      else {
        ctx.fillStyle = colors.blue;
        ctx.globalAlpha = Math.sin(k * Math.PI);
        ctx.fillRect(blink.block.x, blink.block.y, cell, cell);
        ctx.globalAlpha = 1;
        busy = true;
      }
    }
    return busy;
  }

  function loop(now) {
    rafId = 0;
    if (draw(now) && onScreen && !document.hidden) rafId = requestAnimationFrame(loop);
  }
  function wake() {
    if (!rafId && onScreen && !document.hidden) rafId = requestAnimationFrame(loop);
  }

  function scheduleBlink() {
    clearTimeout(blinkTimer);
    if (reduceMotion.matches) return;
    blinkTimer = setTimeout(function () {
      if (onScreen && !document.hidden && blocks.length) {
        blink = { block: blocks[(Math.random() * blocks.length) | 0], t: performance.now() };
        wake();
      }
      scheduleBlink();
    }, 1400 + Math.random() * 1600);
  }

  function onPointer(e) {
    if (e.pointerType !== 'mouse' || reduceMotion.matches) return;
    var r = canvas.getBoundingClientRect();
    var col = Math.floor((e.clientX - r.left) / cell);
    var row = Math.floor((e.clientY - r.top) / cell);
    var key = col + ',' + row;
    if (key === pointer) return;
    pointer = key;
    trail.set(key, performance.now());
    wake();
  }

  // Touch: rings of cells light up outward from the tap, one ring every 55ms.
  var RIPPLE_RINGS = 5;
  function onTap(e) {
    if (e.pointerType === 'mouse' || reduceMotion.matches) return;
    var r = canvas.getBoundingClientRect();
    var col = Math.floor((e.clientX - r.left) / cell);
    var row = Math.floor((e.clientY - r.top) / cell);
    var now = performance.now();
    for (var dy = -RIPPLE_RINGS; dy <= RIPPLE_RINGS; dy++) {
      for (var dx = -RIPPLE_RINGS; dx <= RIPPLE_RINGS; dx++) {
        var ring = Math.abs(dx) + Math.abs(dy); // diamond rings, like blocks being laid
        if (ring > RIPPLE_RINGS) continue;
        trail.set((col + dx) + ',' + (row + dy), now + ring * 55);
      }
    }
    wake();
  }

  function redrawStatic() { draw(performance.now()); }

  readColors();
  layout();
  if (reduceMotion.matches) { settled = true; redrawStatic(); } else wake();

  hero.addEventListener('pointermove', onPointer, { passive: true });
  hero.addEventListener('pointerleave', function () { pointer = null; });
  hero.addEventListener('pointerdown', onTap, { passive: true });

  var resizeTimer = 0;
  new ResizeObserver(function () {
    cancelAnimationFrame(resizeTimer);
    resizeTimer = requestAnimationFrame(function () { layout(); redrawStatic(); wake(); });
  }).observe(hero);

  new IntersectionObserver(function (entries) {
    onScreen = entries[0].isIntersecting;
    if (onScreen) wake();
  }).observe(hero);

  document.addEventListener('visibilitychange', function () { if (!document.hidden) wake(); });
  document.addEventListener('nirmaan:themechange', function () { readColors(); drawGridLayer(); redrawStatic(); });
  reduceMotion.addEventListener('change', function () {
    settled = true; trail.clear(); blink = null; clearTimeout(blinkTimer);
    if (!reduceMotion.matches) scheduleBlink();
    redrawStatic();
  });
})();
