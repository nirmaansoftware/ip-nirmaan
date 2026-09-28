/*
  site.js: behaviour every page needs, motion or not.

  Theme toggle: system, then light, then dark, remembered per browser (the
  same control and icons as nirmaan.online). The saved choice is applied
  before first paint by the inline script in <head>; this wires the button.
  Other scripts redraw on the "nirmaan:themechange" event (hero.js does).
*/
(function () {
  'use strict';

  var root = document.documentElement;
  var KEY = 'ip-nirmaan-theme';
  var LABEL = { system: 'match system', light: 'light', dark: 'dark' };
  var NEXT = { system: 'light', light: 'dark', dark: 'system' };
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-theme-toggle]'));

  function current() {
    var t = root.getAttribute('data-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  }

  function sync() {
    var mode = current();
    buttons.forEach(function (btn) {
      btn.setAttribute('data-mode', mode);
      btn.setAttribute('aria-label', 'Colour theme: ' + LABEL[mode] + '. Switch to ' + LABEL[NEXT[mode]] + '.');
    });
  }

  function apply(mode) {
    if (mode === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);
    try {
      if (mode === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, mode);
    } catch (e) { /* storage blocked: the choice still applies to this page */ }
    sync();
    document.dispatchEvent(new CustomEvent('nirmaan:themechange'));
  }

  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () { apply(NEXT[current()]); });
  });
  sync();

  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (current() === 'system') document.dispatchEvent(new CustomEvent('nirmaan:themechange'));
  });
})();
