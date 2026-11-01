// Typed intro (about 3.5 s). Plays on the first visit in a session only; click or any key skips to the final state.
// The HTML already contains the complete final state, so reduced motion, repeat visits and no-JS need nothing here.
import { h } from "./dom.js";

const SEEN_KEY = "catering.introSeen";
const root = document.querySelector(".intro");
const html = document.documentElement;

if (html.classList.contains("intro-play")) play();

async function play() {
  try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* storage blocked: it just replays next time */ }

  const lines = [...root.querySelectorAll(".intro__line")];
  const texts = lines.map((line) => line.textContent);
  const caret = h("span", { class: "caret", "aria-hidden": "true" });
  let skipped = false;

  const finish = () => {
    if (skipped) return;
    skipped = true;
    caret.remove();
    lines.forEach((line, i) => { line.textContent = texts[i]; line.classList.add("is-struck"); });
    root.classList.add("intro--running", "intro--instant", "intro--show-final", "intro--show-cta");
    cleanup();
  };
  const cleanup = () => {
    document.removeEventListener("click", finish);
    document.removeEventListener("keydown", finish);
  };
  document.addEventListener("click", finish);
  document.addEventListener("keydown", finish);

  const sleep = (ms) => new Promise((resolve) => setTimeout(() => resolve(!skipped), ms));

  // Start from the empty state: a blinking apricot cursor where the first line begins.
  lines.forEach((line) => { line.textContent = ""; line.classList.remove("is-struck"); });
  lines[0].append(caret);
  root.classList.add("intro--running");
  if (!(await sleep(450))) return;

  for (let i = 0; i < lines.length; i++) {
    const text = document.createTextNode("");
    lines[i].textContent = "";
    lines[i].append(text, caret);
    for (const ch of texts[i]) {
      text.data += ch;
      if (!(await sleep(20))) return;
    }
    if (!(await sleep(120))) return;
    lines[i].classList.add("is-struck"); // strike draws right to left, text fades to grey
    if (!(await sleep(300))) return;
  }
  caret.remove();

  root.classList.add("intro--show-final");
  if (!(await sleep(450))) return;
  root.classList.add("intro--show-cta");
  cleanup();
}
