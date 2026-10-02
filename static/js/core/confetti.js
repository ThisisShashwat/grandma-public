import { $$ } from "./dom.js";

/* classic MS Paint colors */
const COLORS = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#000000"];

/* Confetti bursts out of any [data-confetti] button ("big" for the final call to action). */
export function initConfetti() {
  $$("[data-confetti]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (typeof confetti === "undefined") return;
      const r = btn.getBoundingClientRect();
      const big = btn.dataset.confetti === "big";
      confetti({
        particleCount: big ? 140 : 70,
        spread: big ? 100 : 70,
        startVelocity: 35,
        scalar: 1.1,
        shapes: ["square"],
        colors: COLORS,
        origin: { x: (r.left + r.width / 2) / innerWidth, y: (r.top + r.height / 2) / innerHeight },
        disableForReducedMotion: true,
      });
    });
  });
}
