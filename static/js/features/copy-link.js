/* "Share this project" (the share macro in templates/macros/ui.html): the Copy link button copies the address in the box, then says so for two
   seconds. Without JavaScript the box is still read only and selectable by hand (the button stays hidden), so the page works without any of this. */
import { $, $$ } from "../core/dom.js";

const SAID_FOR = 2000;

const selectAndCopy = () => {
  try { return document.execCommand("copy"); } catch { return false; }
};

/* The clipboard API where there is one (it needs a secure page), else the old select-and-copy; false when neither worked. */
async function copy(input) {
  input.select();
  input.setSelectionRange(0, input.value.length);      // iOS ignores select() alone
  try {
    await navigator.clipboard.writeText(input.value);
    return true;
  } catch {
    return selectAndCopy();
  }
}

export function copyLinks() {
  for (const box of $$("[data-copy-link]")) {
    const input = $("input", box);
    const button = $("button", box);
    const label = button.textContent;
    let timer;
    input.addEventListener("click", () => input.select());
    button.hidden = false;
    button.addEventListener("click", async () => {
      button.textContent = (await copy(input)) ? "Copied!" : "Copy it by hand";
      clearTimeout(timer);
      timer = setTimeout(() => { button.textContent = label; }, SAID_FOR);
    });
  }
}
