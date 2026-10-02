import { $$ } from "./dom.js";

/* A dashed box stays until the real image loads. Missing images just keep the box. */
export function initArt() {
  $$(".fig img").forEach((img) => {
    const fig = img.closest(".fig");
    const done = () => fig.classList.remove("ph");
    img.addEventListener("load", done);
    img.addEventListener("error", () => img.remove());
    if (img.complete) { img.naturalWidth ? done() : img.remove(); }
  });
}
