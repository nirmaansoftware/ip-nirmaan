/*
  Motion for the IP Nirmaan landing page. No dependencies.

  Does nothing unless <html> has the "motion" class, which the page sets only
  when the visitor has no reduced-motion preference. The HTML already holds
  every final value (the full plan, the real numbers), so this script only
  ever animates toward what is there; it never supplies content.
*/
(function () {
  'use strict';
  var root = document.documentElement;
  if (!root.classList.contains('motion')) return;

  var reduce = matchMedia('(prefers-reduced-motion: reduce)');
  // If the preference flips mid-visit, drop to the still page at once.
  reduce.addEventListener && reduce.addEventListener('change', function (e) {
    if (e.matches) root.classList.remove('motion');
  });

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // ---- Reveal, section rules, and once-only plays -----------------------
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target;
      if (el.hasAttribute('data-reveal')) el.classList.add('is-in');
      if (el.classList.contains('section')) el.classList.add('is-seen');
      if (el.hasAttribute('data-play')) play(el);
      if (el.classList.contains('stats')) countUp(el);
      io.unobserve(el);
    });
  }, { rootMargin: '0px 0px -12% 0px', threshold: 0.2 });

  document.querySelectorAll('[data-reveal], .section, [data-play], .stats').forEach(function (el) { io.observe(el); });

  // A play runs its CSS timeline once; Replay restarts it from the top.
  function play(el) {
    el.classList.remove('is-playing');
    void el.offsetWidth; // restart CSS animations
    el.classList.add('is-playing');
    var btn = document.querySelector('[data-replay="' + el.getAttribute('data-play') + '"]');
    if (btn) btn.hidden = false;
  }

  document.querySelectorAll('[data-replay]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var name = btn.getAttribute('data-replay');
      if (name === 'term') { printTerminal(); return; }
      var el = document.querySelector('[data-play="' + name + '"]');
      if (el) play(el);
    });
  });

  // ---- Stat tiles count up to the number already in the HTML -------------
  function countUp(list) {
    list.querySelectorAll('[data-count]').forEach(function (el) {
      var target = parseInt(el.getAttribute('data-count'), 10);
      var start = null, dur = 1400;
      el.setAttribute('aria-hidden', 'true');
      var label = el.nextElementSibling;
      if (label) label.setAttribute('aria-label', target + ' ' + label.textContent);
      function step(t) {
        if (start === null) start = t;
        var p = Math.min(1, (t - start) / dur);
        var eased = 1 - Math.pow(1 - p, 4);
        el.textContent = String(Math.round(target * eased));
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = String(target);
      }
      el.textContent = '0';
      requestAnimationFrame(step);
    });
  }

  // ---- Terminal: type the command, then print the plan line by line -----
  var term = document.querySelector('[data-term]');
  var run = 0;

  function printTerminal() {
    if (!term) return;
    var id = ++run;
    var lines = term.querySelectorAll('.ln');
    var cmdLine = term.querySelector('.cmd');
    var typed = term.querySelector('[data-type]');
    var full = typed.getAttribute('data-full') || typed.textContent;
    typed.setAttribute('data-full', full);
    var replay = term.querySelector('[data-replay="term"]');

    lines.forEach(function (l) { l.classList.remove('is-shown'); });
    term.classList.add('is-printing');
    cmdLine.classList.add('is-shown', 'is-typing');
    typed.textContent = '';

    var chain = wait(250);
    for (var i = 1; i <= full.length; i++) {
      (function (n) {
        chain = chain.then(function () {
          if (id !== run) return;
          typed.textContent = full.slice(0, n);
          return wait(22 + (full.charAt(n - 1) === ' ' ? 30 : 0));
        });
      })(i);
    }
    chain = chain.then(function () { return wait(380); }).then(function () {
      if (id !== run) return;
      cmdLine.classList.remove('is-typing');
    });
    Array.prototype.slice.call(lines, 1).forEach(function (l) {
      chain = chain.then(function () {
        if (id !== run) return;
        l.classList.add('is-shown');
        return wait(l.querySelector('.gate') ? 260 : 75);
      });
    });
    chain.then(function () {
      if (id !== run) return;
      term.classList.remove('is-printing');
      if (replay) replay.hidden = false;
    });
  }

  // ---- How it works: a pinned scene scrubbed by scroll -------------------
  // Scroll through the tall track turns into progress p (0 to 1). Each
  // [data-at="a b"] element gets --t, its own 0 to 1 over that span; each
  // task shows the last state whose time has passed; the step being told is
  // marked current. The HTML holds the finished diagram, so p = 1 is simply
  // the page as written.
  var scene = document.querySelector('[data-scene]');
  if (scene) {
    var track = scene.querySelector('.scene__track');
    var sticky = scene.querySelector('.scene__sticky');
    var body = scene.querySelector('.scene__body');
    var nav = document.querySelector('.nav');
    var span = function (el, attr) { var r = el.getAttribute(attr).split(' ').map(Number); return { el: el, a: r[0], b: r[1] }; };
    var timed = Array.prototype.map.call(scene.querySelectorAll('[data-at]'), function (el) { return span(el, 'data-at'); });
    var steps = Array.prototype.map.call(scene.querySelectorAll('[data-span]'), function (el) { return span(el, 'data-span'); });
    var tasks = Array.prototype.map.call(scene.querySelectorAll('[data-states]'), function (el) {
      return { chip: el.querySelector('.task__state'), states: JSON.parse(el.getAttribute('data-states')) };
    });
    var clamp01 = function (v) { return v < 0 ? 0 : v > 1 ? 1 : v; };
    var pinned = true, queued = false;

    tasks.forEach(function (t) {
      t.chip.addEventListener('animationend', function () { t.chip.classList.remove('is-changed'); });
    });

    function layoutScene() {
      // Pin when the scene fits on screen, shrinking it a little (zoom) when
      // it nearly fits; otherwise it plays in normal flow as it scrolls past.
      scene.classList.remove('scene--unpinned');
      body.style.setProperty('--fit', '1');
      render(progress()); // phones show only the current step: measure that
      var fit = (window.innerHeight - nav.offsetHeight - 16) / body.offsetHeight;
      pinned = fit >= 0.72;
      body.style.setProperty('--fit', pinned ? Math.min(1, fit).toFixed(3) : '1');
      scene.classList.toggle('scene--unpinned', !pinned);
    }

    function progress() {
      if (pinned) {
        var total = track.offsetHeight - sticky.offsetHeight;
        return total > 0 ? clamp01((nav.offsetHeight - track.getBoundingClientRect().top) / total) : 1;
      }
      var r = body.getBoundingClientRect(), vh = window.innerHeight;
      return clamp01((vh * 0.85 - r.top) / (r.height + vh * 0.1));
    }

    function render(p) {
      timed.forEach(function (x) { x.el.style.setProperty('--t', clamp01((p - x.a) / (x.b - x.a)).toFixed(3)); });
      steps.forEach(function (x) {
        x.el.classList.toggle('is-current', p >= x.a && p < x.b);
        x.el.classList.toggle('is-done', p >= x.b);
      });
      tasks.forEach(function (t) {
        var state = t.states[0][1];
        t.states.forEach(function (s) { if (p >= s[0]) state = s[1]; });
        if (t.chip.getAttribute('data-state') !== state) {
          t.chip.setAttribute('data-state', state);
          t.chip.textContent = state;
          t.chip.classList.add('is-changed');
        }
      });
    }

    function frame() { queued = false; render(progress()); }
    function queue() { if (!queued) { queued = true; requestAnimationFrame(frame); } }

    layoutScene();
    frame();
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', function () { layoutScene(); queue(); });
    reduce.addEventListener && reduce.addEventListener('change', function (e) { if (e.matches) render(1); });
  }

  if (term) {
    // Hold the plan hidden from the first frame, then print once the hero has arrived.
    term.classList.add('is-printing');
    wait(700).then(printTerminal);
  }
})();
