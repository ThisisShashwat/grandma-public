import { $, $$, el, shuffle } from "../core/dom.js";
import { reduce, finePointer, hasGsap, hasDrag } from "../core/env.js";

const NOTE_COUNT = 6;

/* The fridge demo: six notes dealt from the pool, draggable, "Ask again" re-deals. It is a demo only:
   the real draw has to happen on the server. Needs #fridge, #ask, #askStatus and the .ask-fig Grandmas
   (note pull, magnifier, eye roll, shocked, nose up). */
export function initFridge({ pool, tiers, freeAsks }) {
  const fridge = $("#fridge");
  const notes = Array.from({ length: NOTE_COUNT }, () => {
    const n = document.createElement("div");
    n.className = "note";
    n.style.setProperty("--rot", (Math.random() * 6 - 3).toFixed(1));
    fridge.append(n);
    return n;
  });

  const deal = () => {
    shuffle([...pool]).slice(0, NOTE_COUNT).forEach(([name, line, tier], i) => {
      notes[i].replaceChildren(el("b", name), line, el("span", tiers[tier], "tier"));
    });
    if (hasGsap) {
      gsap.set(notes, { x: 0, y: 0 });
      if (!reduce) gsap.from(notes, { scale: 0.6, rotation: -8, duration: 0.4, ease: "steps(5)", stagger: 0.06 });
    }
  };
  deal();

  if (hasGsap && hasDrag && finePointer) {
    let z = 10;
    Draggable.create(notes, {
      bounds: fridge,
      edgeResistance: 0.85,
      cursor: "grab",
      activeCursor: "grabbing",
      zIndexBoost: false,
      onPress() { this.target.style.zIndex = ++z; },
    });
  }

  let asks = 0;
  const figs = $$(".ask-fig");
  $("#ask").addEventListener("click", () => {
    asks++;
    const shown = Math.min(asks, figs.length - 1);
    figs.forEach((f, i) => { f.hidden = i !== shown; });
    if (hasGsap && !reduce) gsap.from(figs[shown], { scale: 0.85, rotation: -4, duration: 0.3, ease: "steps(3)" });
    $("#askStatus").textContent = asks > freeAsks
      ? "That's enough, dear. In the real thing, more asks cost cookies."
      : `Ask ${asks} of ${freeAsks} free.`;
    deal();
  });
}
