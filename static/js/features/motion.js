import { reduce, hasGsap } from "../core/env.js";

/* The chunky MS Paint motion (steps() easing). Skipped for reduced motion. */
const animated = hasGsap && !reduce;

/* hero: everything pops in, then the spoon wiggles */
export function heroMotion() {
  if (!animated) return;
  gsap.from(".hero .fig", {
    scale: 0.5, rotation: -10, opacity: 0,
    duration: 0.6, ease: "steps(6)", stagger: 0.15, transformOrigin: "50% 100%",
  });
  gsap.to(".js-wiggle", {
    rotation: 2.5, duration: 0.45, repeat: -1, yoyo: true,
    ease: "steps(2)", transformOrigin: "50% 100%", delay: 1.4,
  });
}

/* Hack Club section: Grandma's phone shakes with outrage */
export function phoneShake() {
  if (!animated) return;
  gsap.to(".js-phone", { rotation: -2, duration: 0.3, repeat: -1, yoyo: true, ease: "steps(2)", transformOrigin: "50% 100%" });
}
