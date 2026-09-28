/*
  site.js: shared behaviour for every page.

    1. Nav state: border once scrolled, reading-progress bar
    2. Theme toggle: system → light → dark, remembered per browser
    3. Mobile menu: focus management, Escape, scroll lock
    4. Scroll reveal: [data-reveal] elements rise in once; section rules draw
       across as each section arrives; cards get a pointer spotlight.
       Prices never animate: the figure a visitor sees is always the real one.
    5. Scroll scenes, all driven from one rAF-throttled scroll loop:
         [data-scene="stack"]     layer tower builds as you scroll (pinned); on
                                  narrower screens the layer you're reading lights up
         [data-scene="rail"]      services track moves sideways (pinned, all widths)
         [data-scene="line"]      process timeline fills as it passes
         [data-scene="spy"]       process index highlights the step in view
         [data-scene="build"]     problem → system story, scrubbed by scroll (pinned)

  Everything here is progressive enhancement. With JS off, or with reduced
  motion, every section renders fully built and in normal document flow.
*/
(function () {
  'use strict';

  var root = document.documentElement;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var wide = window.matchMedia('(min-width: 60.001rem)');
  var clamp01 = function (v) { return v < 0 ? 0 : v > 1 ? 1 : v; };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };

  /* ---------------------------------------------------------------
     2. Theme toggle
  --------------------------------------------------------------- */
  var THEME_KEY = 'nirmaan-theme';
  var THEME_LABEL = { system: 'match system', light: 'light', dark: 'dark' };
  var THEME_NEXT = { system: 'light', light: 'dark', dark: 'system' };

  function currentTheme() {
    var t = root.getAttribute('data-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  }
  function applyTheme(mode) {
    if (mode === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);
    try {
      if (mode === 'system') localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, mode);
    } catch (e) { /* storage blocked: the choice still applies to this page */ }
    syncThemeButtons();
    document.dispatchEvent(new CustomEvent('nirmaan:themechange'));
  }
  function syncThemeButtons() {
    var mode = currentTheme();
    $$('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('data-mode', mode);
      btn.setAttribute('aria-label', 'Colour theme: ' + THEME_LABEL[mode] + '. Switch to ' + THEME_LABEL[THEME_NEXT[mode]] + '.');
    });
  }
  $$('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () { applyTheme(THEME_NEXT[currentTheme()]); });
  });
  syncThemeButtons();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (currentTheme() === 'system') document.dispatchEvent(new CustomEvent('nirmaan:themechange'));
  });

  /* ---------------------------------------------------------------
     3. Mobile menu
  --------------------------------------------------------------- */
  var menu = document.querySelector('[data-menu]');
  var menuBtn = document.querySelector('[data-menu-toggle]');

  function setMenu(open, restoreFocus) {
    if (!menu || !menuBtn) return;
    menuBtn.setAttribute('aria-expanded', String(open));
    menu.hidden = !open;
    root.classList.toggle('menu-open', open);
    if (open) {
      // Next frame so the entrance animation runs from the un-hidden state.
      requestAnimationFrame(function () { menu.classList.add('is-open'); });
      var first = menu.querySelector('a');
      if (first) first.focus();
    } else {
      menu.classList.remove('is-open');
      if (restoreFocus) menuBtn.focus();
    }
  }
  if (menu && menuBtn) {
    menuBtn.addEventListener('click', function () {
      setMenu(menuBtn.getAttribute('aria-expanded') !== 'true', true);
    });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a')) setMenu(false, false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !menu.hidden) setMenu(false, true);
      // Keep Tab inside the open sheet (plus the toggle that closes it).
      if (e.key === 'Tab' && !menu.hidden) {
        var stops = [menuBtn].concat($$('a', menu));
        var i = stops.indexOf(document.activeElement);
        var next = e.shiftKey ? (i <= 0 ? stops.length - 1 : i - 1) : (i === stops.length - 1 ? 0 : i + 1);
        e.preventDefault();
        stops[next].focus();
      }
    });
    window.matchMedia('(min-width: 64.001rem)').addEventListener('change', function (e) {
      if (e.matches) setMenu(false, false);
    });
  }

  /* ---------------------------------------------------------------
     4. Scroll reveal
  --------------------------------------------------------------- */
  if (root.classList.contains('motion')) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        // In a swipe row the cards still off to the side never intersect, and
        // left lowered they'd give the row vertical overflow that swallows the
        // page's scroll on phones. They rise together with the first one.
        var row = entry.target.parentElement && entry.target.parentElement.closest('[data-swipe]');
        var group = row ? $$('[data-reveal]', row) : [entry.target];
        group.forEach(function (el) {
          el.classList.add('is-in');
          revealObserver.unobserve(el);
        });
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.01 });
    $$('[data-reveal]').forEach(function (el) { revealObserver.observe(el); });

    // Section rules: drawn once the section's top edge is on screen.
    var ruleObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-seen');
        ruleObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -12% 0px' });
    $$('.section + .section').forEach(function (el) { ruleObserver.observe(el); });
  }

  /* Pointer spotlight: a soft light follows the pointer across cards. */
  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    var SPOT = '.price-card, .package, .care-card, .care-link, .plan-switch__item, .included__group, .fit__other, .principles li, .svc-card, .includes li, .gets__list li';
    $$(SPOT).forEach(function (el) { el.classList.add('has-spot'); });
    document.addEventListener('pointermove', function (e) {
      var card = e.target.closest && e.target.closest('.has-spot');
      if (!card) return;
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, { passive: true });
  }

  /* ---------------------------------------------------------------
     4b. Phones: swipe rows and the dock
  --------------------------------------------------------------- */
  // Swipe rows ([data-swipe], horizontal on phones in styles.css): dots that
  // follow the swipe and jump to a card, plus a "2 / 4" count.
  $$('[data-swipe]').forEach(function (list) {
    var items = Array.prototype.slice.call(list.children);
    if (items.length < 2) return;
    var bar = document.createElement('div');
    bar.className = 'swipe-dots';
    var track = document.createElement('div');
    track.className = 'swipe-dots__track';
    var count = document.createElement('span');
    count.className = 'mono swipe-dots__count';
    count.setAttribute('aria-hidden', 'true');
    var label = list.getAttribute('aria-label') || 'item';
    var dots = items.map(function (item, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', label + ': ' + (i + 1) + ' of ' + items.length);
      b.addEventListener('click', function () {
        list.scrollTo({ left: item.offsetLeft - list.offsetLeft - parseFloat(getComputedStyle(list).scrollPaddingLeft || 0), behavior: reduceMotion.matches ? 'auto' : 'smooth' });
      });
      track.appendChild(b);
      return b;
    });
    bar.appendChild(track);
    bar.appendChild(count);
    list.insertAdjacentElement('afterend', bar);

    // A row of plain text cards has nothing to tab to, so keyboard users
    // couldn't scroll it; make the row itself focusable where it scrolls.
    if (!list.querySelector('a[href], button, input, select, textarea, [tabindex]')) {
      var phoneRow = window.matchMedia('(max-width: 40rem)');
      var syncTab = function () {
        if (phoneRow.matches) list.setAttribute('tabindex', '0');
        else list.removeAttribute('tabindex');
      };
      phoneRow.addEventListener('change', syncTab);
      syncTab();
    }

    var current = -1;
    function sync() {
      var edge = list.getBoundingClientRect().left + parseFloat(getComputedStyle(list).scrollPaddingLeft || 0);
      var best = 0, bestD = Infinity;
      items.forEach(function (item, i) {
        var d = Math.abs(item.getBoundingClientRect().left - edge);
        if (d < bestD) { bestD = d; best = i; }
      });
      // At the far end the last card may never reach the edge; count it anyway.
      if (list.scrollLeft + list.clientWidth >= list.scrollWidth - 4) best = items.length - 1;
      if (best === current) return;
      current = best;
      dots.forEach(function (b, i) { b.setAttribute('aria-current', String(i === best)); });
      count.textContent = (best + 1) + ' / ' + items.length;
    }
    var pending = false;
    list.addEventListener('scroll', function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () { pending = false; sync(); });
    }, { passive: true });
    sync();
  });

  // The dock: shown once the page's first screen of buttons has scrolled
  // away, hidden again when the closing call to action or footer is in view
  // (they already offer the same step).
  var dock = document.querySelector('[data-dock]');
  if (dock && 'IntersectionObserver' in window) {
    var opener = document.querySelector('.hero .actions') || document.querySelector('.page-head .actions') || document.querySelector('.page-head');
    var closers = $$('.cta-band, .footer');
    var openerGone = false, closerSeen = new Set();
    function syncDock() { dock.classList.toggle('is-shown', openerGone && closerSeen.size === 0); }
    if (opener) {
      new IntersectionObserver(function (entries) {
        var e = entries[0];
        openerGone = !e.isIntersecting && e.boundingClientRect.top < 0;
        syncDock();
      }, { rootMargin: '-' + ((document.querySelector('[data-nav]') || {}).offsetHeight || 0) + 'px 0px 0px 0px' }).observe(opener);
    } else { openerGone = true; }
    var closerObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) closerSeen.add(e.target); else closerSeen.delete(e.target); });
      syncDock();
    });
    closers.forEach(function (c) { closerObserver.observe(c); });
    syncDock();
  }

  /* ---------------------------------------------------------------
     5. Scroll scenes
  --------------------------------------------------------------- */
  var nav = document.querySelector('[data-nav]');
  var progressBar = document.querySelector('[data-scroll-progress]');
  var scenes = [];

  // Progress of an element's scroll through the viewport while pinned:
  // 0 when its top reaches the nav, 1 when its bottom reaches the viewport bottom.
  function pinProgress(el) {
    var r = el.getBoundingClientRect();
    var navH = nav ? nav.offsetHeight : 0;
    var travel = r.height - (window.innerHeight - navH);
    return travel > 0 ? clamp01((navH - r.top) / travel) : 0;
  }
  function canPin() { return wide.matches && !reduceMotion.matches; }

  /* Layer stack: 5 layers placed one per fifth of the pinned scroll. Below the
     pinning width nothing is pinned: every layer is shown, and the one under
     the reading line (just above the middle of the screen) is highlighted,
     so the highlight follows your thumb down the page, top to bottom. */
  $$('[data-scene="stack"]').forEach(function (el) {
    var layers = $$('[data-layer]', el);
    var meter = $$('[data-meter] span', el);
    var count = el.querySelector('[data-stack-count]');
    var n = layers.length;
    var last = -1;

    function set(k, current) {
      var key = k + ':' + current;
      if (key === last) return;
      last = key;
      layers.forEach(function (layer, i) {
        layer.classList.toggle('is-placed', i <= k);
        layer.classList.toggle('is-current', i === current);
      });
      meter.forEach(function (m, i) { m.classList.toggle('is-on', i <= k); });
      if (count) count.textContent = (k + 1) + ' / ' + n;
    }

    // The layer nearest the reading line; -1 while the tower is off that line.
    function underReadingLine() {
      var line = window.innerHeight * 0.45, best = -1, bestD = Infinity;
      layers.forEach(function (layer, i) {
        var r = layer.getBoundingClientRect();
        if (r.bottom < line - r.height || r.top > line + r.height) return;
        var d = Math.abs((r.top + r.bottom) / 2 - line);
        if (d < bestD) { bestD = d; best = i; }
      });
      return best;
    }

    scenes.push({
      el: el,
      layout: function () {
        el.classList.toggle('is-pinned', canPin());
        last = -1;
        if (!canPin()) set(n - 1, reduceMotion.matches ? -1 : underReadingLine());
      },
      update: function () {
        if (canPin()) {
          var k = Math.min(n - 1, Math.floor(pinProgress(el) * n));
          return set(k, k);
        }
        if (!reduceMotion.matches) set(n - 1, underReadingLine());
      },
    });
  });

  /* Services rail: vertical scroll drives the track sideways, on every screen
     tall enough to hold it (phones included), not only wide ones. */
  function canPinRail() { return !reduceMotion.matches && window.innerHeight >= 520; }
  $$('[data-scene="rail"]').forEach(function (el) {
    var viewport = el.querySelector('[data-rail-viewport]');
    var track = el.querySelector('[data-rail-track]');
    var distance = 0;

    scenes.push({
      el: el,
      layout: function () {
        var pin = canPinRail();
        el.classList.toggle('is-pinned', pin);
        el.style.height = '';
        if (!pin) { el.style.setProperty('--rail', '0'); return; }
        distance = Math.max(0, track.scrollWidth - viewport.clientWidth);
        el.style.setProperty('--rail-distance', distance + 'px');
        // Pinned height = one screen + the sideways distance, so 1px down = 1px across.
        el.style.height = (el.querySelector('.rail__sticky').offsetHeight + distance) + 'px';
      },
      update: function () {
        if (canPinRail()) { el.style.setProperty('--rail', pinProgress(el).toFixed(4)); return; }
        var max = viewport.scrollWidth - viewport.clientWidth;
        el.style.setProperty('--rail', max > 0 ? (viewport.scrollLeft / max).toFixed(4) : '0');
      },
    });
    viewport.addEventListener('scroll', function () { schedule(); }, { passive: true });
  });

  /* Problem → system: pinned, and scroll position p (0 to 1) tells the
     story. Each [data-at="a b"] element gets --t, its own 0 to 1 over that
     span; each order shows the last status whose time has passed; the beat
     being told is current. The HTML is the finished state, so p = 1 is the
     page as written. Pinned only when it fits on screen (zoomed down a
     little if it nearly fits); otherwise it stays a still before-and-after. */
  $$('[data-scene="build"]').forEach(function (el) {
    var grid = el.querySelector('.build__grid');
    var dock = document.querySelector('[data-dock]');
    var span = function (node, attr) { var r = node.getAttribute(attr).split(' ').map(Number); return { el: node, a: r[0], b: r[1] }; };
    var timed = $$('[data-at]', el).map(function (n) { return span(n, 'data-at'); });
    var beats = $$('[data-span]', el).map(function (n) { return span(n, 'data-span'); });
    var orders = $$('[data-states]', el).map(function (n) {
      var chip = n.querySelector('.order__state');
      chip.addEventListener('animationend', function () { chip.classList.remove('is-changed'); });
      return { chip: chip, states: JSON.parse(n.getAttribute('data-states')) };
    });
    var pinned = false;

    function render(p) {
      timed.forEach(function (x) { x.el.style.setProperty('--t', clamp01((p - x.a) / (x.b - x.a)).toFixed(3)); });
      beats.forEach(function (x) {
        x.el.classList.toggle('is-current', p >= x.a && p < x.b);
        x.el.classList.toggle('is-done', p >= x.b);
      });
      orders.forEach(function (o) {
        var state = o.states[0][1];
        o.states.forEach(function (st) { if (p >= st[0]) state = st[1]; });
        if (o.chip.getAttribute('data-state') !== state) {
          o.chip.setAttribute('data-state', state);
          o.chip.textContent = state;
          o.chip.classList.add('is-changed');
        }
      });
      el.classList.toggle('is-built', p >= 0.5);
      el.style.setProperty('--swap', clamp01((p - 0.47) / 0.06).toFixed(3));
    }

    scenes.push({
      el: el,
      layout: function () {
        el.classList.remove('is-pinned');
        el.style.removeProperty('--fit');
        pinned = false;
        if (!reduceMotion.matches) {
          el.classList.add('is-pinned');
          // Phones show one beat at a time, and the scene's height changes
          // from beat to beat: fit the tallest.
          var tallest = 0;
          beats.forEach(function (x) { render((x.a + Math.min(1, x.b)) / 2); tallest = Math.max(tallest, grid.offsetHeight); });
          render(pinProgress(el));
          // Leave room for the phone dock, which sits over the bottom of the screen.
          var dockH = dock && getComputedStyle(dock).display !== 'none' ? dock.offsetHeight : 0;
          el.style.setProperty('--dock-h', dockH + 'px');
          var fit = (window.innerHeight - (nav ? nav.offsetHeight : 0) - dockH - 16) / tallest;
          pinned = fit >= 0.72;
          if (pinned) el.style.setProperty('--fit', Math.min(1, fit).toFixed(3));
          else el.classList.remove('is-pinned');
        }
        if (!pinned) render(1);
      },
      update: function () { if (pinned) render(pinProgress(el)); },
    });
  });

  /* Timeline line: fills as the list crosses the middle of the screen, and
     marks each step .is-reached once the line gets to it. */
  $$('[data-scene="line"]').forEach(function (el) {
    var steps = $$('ol > li', el);
    function reach(p) {
      steps.forEach(function (li, i) { li.classList.toggle('is-reached', p >= (i + 0.35) / steps.length); });
    }
    scenes.push({
      el: el,
      layout: function () {},
      update: function () {
        if (reduceMotion.matches) { el.style.setProperty('--progress-line', '1'); reach(1); return; }
        var r = el.getBoundingClientRect();
        var vh = window.innerHeight;
        var p = clamp01((vh * 0.8 - r.top) / (r.height + vh * 0.35));
        el.style.setProperty('--progress-line', p.toFixed(4));
        reach(p);
      },
    });
  });

  /* Scroll spy: highlights the index link of the step nearest the top third */
  $$('[data-scene="spy"]').forEach(function (el) {
    var links = $$('a[href^="#"]', el);
    var targets = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
    scenes.push({
      el: el.parentElement,
      layout: function () {},
      update: function () {
        var line = window.innerHeight * 0.35;
        var active = 0;
        targets.forEach(function (t, i) { if (t && t.getBoundingClientRect().top <= line) active = i; });
        links.forEach(function (a, i) {
          a.classList.toggle('is-active', i === active);
          if (i === active) a.setAttribute('aria-current', 'step'); else a.removeAttribute('aria-current');
        });
      },
    });
  });

  /* Only scenes near the viewport do work each frame. */
  var visible = new Set();
  if ('IntersectionObserver' in window) {
    var sceneObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var scene = scenes.filter(function (s) { return s.el === entry.target; });
        scene.forEach(function (s) { if (entry.isIntersecting) visible.add(s); else visible.delete(s); });
      });
      schedule();
    }, { rootMargin: '25% 0px 25% 0px' });
    scenes.forEach(function (s) { sceneObserver.observe(s.el); });
  } else {
    scenes.forEach(function (s) { visible.add(s); });
  }

  var ticking = false;
  function frame() {
    ticking = false;
    var y = window.scrollY;
    if (nav) nav.classList.toggle('is-scrolled', y > 8);
    if (progressBar) {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      progressBar.style.setProperty('--progress', max > 0 ? clamp01(y / max).toFixed(4) : '0');
    }
    visible.forEach(function (s) { s.update(); });
  }
  function schedule() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(frame);
  }
  function relayout() {
    scenes.forEach(function (s) { s.layout(); s.update(); });
    schedule();
  }

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', relayout);
  wide.addEventListener('change', relayout);
  reduceMotion.addEventListener('change', relayout);
  // Web fonts change card widths, which changes the rail's travel distance.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(relayout);
  relayout();
})();
