import { $$, el } from "./dom.js";
import { dev, hasGsap, hasDrag } from "./env.js";

/* Dev mode: open any page with ?dev. Drag art to place it, scroll over it to resize.
   Copy the printed numbers into the figure's `pos` text (or style attribute). */
export function initDev() {
  if (!(dev && hasGsap && hasDrag)) return;
  document.documentElement.classList.add("dev");
  const out = el("pre", "dev mode: drag art to place it, scroll over it to resize", "dev-out");
  document.body.append(out);
  const num = (fig, name, fallback) => parseFloat(fig.style.getPropertyValue(name)) || fallback;
  const report = (fig) => {
    out.textContent = `${fig.dataset.file}\nstyle="--x: ${num(fig, "--x", 0)}; --y: ${num(fig, "--y", 0)}; --w: ${num(fig, "--w", 30)}"`;
  };
  $$(".fig.abs").forEach((fig) => {
    Draggable.create(fig, {
      type: "x,y",
      onDragEnd() {
        const stage = fig.closest(".stage").getBoundingClientRect();
        const box = fig.getBoundingClientRect();
        fig.style.setProperty("--x", (((box.left - stage.left) / stage.width) * 100).toFixed(1));
        fig.style.setProperty("--y", (((box.top - stage.top) / stage.height) * 100).toFixed(1));
        gsap.set(fig, { x: 0, y: 0 });
        report(fig);
      },
    });
    fig.addEventListener("wheel", (e) => {
      e.preventDefault();
      const w = Math.max(5, num(fig, "--w", 30) + (e.deltaY < 0 ? 1 : -1));
      fig.style.setProperty("--w", w);
      report(fig);
    }, { passive: false });
  });
}
