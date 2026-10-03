import { $$ } from "./dom.js";

/* classic MS Paint colors */
const COLORS = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#000000"];

/* A burst of square MS Paint confetti from `origin` ({x, y} as fractions of the window). The library is optional, and it stays
   quiet for people who asked their system for less motion. */
export function burst(origin, big = false) {
  if (typeof confetti === "undefined") return;
  confetti({
    particleCount: big ? 140 : 70,
    spread: big ? 100 : 70,
    startVelocity: 35,
    scalar: 1.1,
    shapes: ["square"],
    colors: COLORS,
    origin,
    disableForReducedMotion: true,
  });
}

/* Confetti bursts out of any [data-confetti] button ("big" for the final call to action). */
export function initConfetti() {
  $$("[data-confetti]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const r = btn.getBoundingClientRect();
      burst({ x: (r.left + r.width / 2) / innerWidth, y: (r.top + r.height / 2) / innerHeight }, btn.dataset.confetti === "big");
    });
  });
}
