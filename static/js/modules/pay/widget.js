/* Wires the calculator markup (templates/components/calculator.html) to the maths.
   Nothing here touches the page until you call mount(), so any page can load it.

     import { createPay } from "./math.js"; import { mount } from "./widget.js";
     mount(document.querySelector("[data-pay-root]"), { pay: createPay(data.pay), faces: data.faces, tiers: data.tiers, levels: data.levels });

   Markup contract (all inside one root element):
     [data-pay="slot"] x3        demand notes, tap to cycle mild / medium / spicy / none
     [data-pay="hours"]          <input type="range">
     [data-pay="hours-out"]      shows the hours
     [data-pay="total"]          shows the cookies
     [data-pay="say"]            Grandma's one-liner
     [data-pay="huge"]           lights up by itself at 20 hours and up
     [data-pay="quality"] and [data-pay="ribbon"]    toggle buttons (aria-pressed)
     [data-face="furious" ... "overjoyed"]           one figure per face, only one is shown
   Fires a "pay:change" event on the root with { x, cookies, face, hours }.
   Options: reduceMotion, gsap (defaults: the user's setting, the global). */
export function mount(rootEl, { pay, faces, tiers, levels, reduceMotion, gsap: g } = {}) {
  if (!rootEl) return null;
  const one = (n) => rootEl.querySelector(`[data-pay="${n}"]`);
  const slots = [...rootEl.querySelectorAll('[data-pay="slot"]')];
  const hoursEl = one("hours");
  const totalEl = one("total");
  const sayEl = one("say");
  const hoursOut = one("hours-out");
  const hugeEl = one("huge");
  const buttons = { quality: one("quality"), ribbon: one("ribbon") };
  const figs = {};
  rootEl.querySelectorAll("[data-face]").forEach((f) => { figs[f.dataset.face] = f; });

  const reduce = reduceMotion !== undefined ? reduceMotion : matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (g === undefined) g = typeof gsap !== "undefined" ? gsap : null;
  const animate = !!g && !reduce;

  const picked = [0, 0, 0];
  const flag = { quality: false, ribbon: false };
  const shown = { cookies: 0, face: -1 };
  const state = () => ({ tiers: [...picked], hours: Number(hoursEl.value), quality: flag.quality, ribbon: flag.ribbon, hoursMax: Number(hoursEl.max) || pay.config.hoursMax });

  const text = (tag, t) => { const e = document.createElement(tag); e.textContent = t; return e; };
  const showCookies = (n) => { totalEl.textContent = Math.round(n).toLocaleString(); };

  const update = (first) => {
    const s = state();
    const x = pay.xFor(s);
    const total = pay.cookies(s);
    const f = pay.face(s);
    hoursOut.textContent = s.hours;
    hugeEl.setAttribute("aria-pressed", String(s.hours >= pay.config.hugeHours));

    if (animate && !first) {
      g.to(shown, { cookies: total, duration: 0.35, ease: "steps(6)", overwrite: true, onUpdate: () => showCookies(shown.cookies) });
    } else {
      shown.cookies = total;
      showCookies(total);
    }

    faces.forEach((def, i) => { if (figs[def.name]) figs[def.name].hidden = i !== f; });
    sayEl.textContent = faces[f].say;
    if (animate && !first && f !== shown.face && figs[faces[f].name]) {
      g.fromTo(figs[faces[f].name], { scale: 0.92 }, { scale: 1, duration: 0.3, ease: "steps(3)", transformOrigin: "50% 100%" });
    }
    shown.face = f;
    rootEl.dispatchEvent(new CustomEvent("pay:change", { detail: { x, cookies: total, face: f, hours: s.hours } }));
  };

  /* tap a note: mild, medium, spicy, then clear. The next note appears once this one is filled. */
  const defaults = [["Add a demand", "tap me"], ["Another one?", "optional"], ["One more?", "if you dare"]];
  const paintSlots = () => {
    slots.forEach((s, i) => {
      s.hidden = i > 0 && !picked[i - 1];
      const t = picked[i];
      s.toggleAttribute("data-tier", !!t);
      if (t) s.dataset.tier = t;
      s.replaceChildren(text("b", t ? tiers[t] : defaults[i][0]), text("span", t ? levels[t] : defaults[i][1]));
    });
  };
  slots.forEach((s, i) => s.addEventListener("click", () => {
    picked[i] = (picked[i] + 1) % 4;
    if (!picked[i]) picked.fill(0, i + 1);     // clearing a note clears the ones after it
    paintSlots();
    update();
  }));

  Object.keys(buttons).forEach((key) => {
    const b = buttons[key];
    if (!b) return;
    b.addEventListener("click", () => {
      flag[key] = !flag[key];
      b.setAttribute("aria-pressed", String(flag[key]));
      update();
    });
  });
  hoursEl.addEventListener("input", () => update());

  paintSlots();
  update(true);
  return { update: () => update(), state };
}
