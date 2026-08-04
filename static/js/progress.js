/* Standalone /progress page. The real progress display lives on the Upload
 * page (which starts the upload); this route only exists so the page is
 * directly reachable (e.g. a bookmark or a reload) and, per the "empty
 * states" requirement, guides the teacher back to Upload when there is
 * nothing in flight. */
(() => {
  const emptyEl = document.getElementById("progress-empty");
  const activeEl = document.getElementById("progress-active");
  if (emptyEl && activeEl) {
    activeEl.hidden = true;
    emptyEl.hidden = false;
  }
})();
