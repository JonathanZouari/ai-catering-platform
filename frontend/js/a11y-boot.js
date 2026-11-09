// Applies the visitor's saved accessibility settings before the first paint, so the page never flashes
// in the default look. Classic script (not a module) loaded in <head>. The menu that changes these
// settings is js/lib/a11y-menu.js; both read the same key and the same class names.
(function () {
  try {
    var saved = JSON.parse(localStorage.getItem("yumm.a11y.v1"));
    if (!saved) return;
    var root = document.documentElement;
    if (saved.size === 1 || saved.size === 2) root.classList.add("a11y-size-" + saved.size);
    if (saved.contrast) root.classList.add("a11y-contrast");
    if (saved.motion) root.classList.add("a11y-no-motion");
    if (saved.links) root.classList.add("a11y-links");
  } catch (e) {
    // Storage blocked or the value is corrupt: keep the default look.
  }
})();
