// Accent comparison helper: ?accent=apricot | sea | klein. Classic script in <head> so there is no flash.
// Unknown values are ignored (CSS only defines these three); no param = default blue.
(function () {
  var accent = new URLSearchParams(location.search).get("accent");
  if (accent === "apricot" || accent === "sea" || accent === "klein") document.documentElement.dataset.accent = accent;
})();
