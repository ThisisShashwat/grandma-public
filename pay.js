/* Grandma's payout calculator: the numbers, the maths and Grandma's face, in one reusable file.
   Nothing here touches the page until you call GrandmaPay.mount(), so any page can load it.

   Use it on another page:
     <script defer src="pay.js"></script>
     GrandmaPay.mount(document.querySelector("[data-pay-root]"));     // wires the markup (see index.html, #pay)
   or skip the markup and just use the maths:
     GrandmaPay.cookies({ tiers: [2, 3], hours: 24, quality: true, ribbon: false })   // cookies for those hours
     GrandmaPay.face({ tiers: [2, 3], hours: 24, quality: true })                     // 0 to 9, see FACES

   The formula comes from the "Modifiers ysws" PDF and must not change:
     x          = demands (0.1 / 0.2 / 0.3 each) + cool 0.2 + huge 0.1 (at 20 hours and up) + Blue Ribbon 0.1, at most xmax
     multiplier = 1 + (cap - 1) * (1 - e^(-k x)) / (1 - e^(-k xmax))
     cookies    = base * multiplier * 10 * hours       (dollars are never shown anywhere) */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;   // node, for tests
  else root.GrandmaPay = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CONFIG = {
    base: 3.25,            // base rate per hour in USD, internal only
    cap: 1.85,             // multiplier at x = xmax
    k: -0.8,               // curve steepness from the PDF. Negative = back-loaded: most projects sit low, stacked ones climb
    xmax: 1.3,             // 3 x 0.3 (demands) + 0.2 + 0.1 + 0.1 (bonuses): the biggest x anyone can reach
    tier: { 1: 0.1, 2: 0.2, 3: 0.3 },   // x per demand: the 1.1x, 1.2x, 1.3x tiers
    quality: 0.2,          // "cool / high quality project" (1.2x)
    huge: 0.1,             // huge project (1.1x) ...
    hugeHours: 20,         // ... at this many hours and above
    ribbon: 0.1,           // Blue Ribbon, the old Star (1.1x)
    cookiesPerUsd: 10,

    /* Grandma's face (look only, never changes a payout). Score = demands and hours, each as a share of its maximum. */
    hoursMax: 60,          // the hours slider's maximum, so 60 hours counts as "all the hours"
    demandWeight: 0.6,
    hoursWeight: 0.4,
    faceAt: [0.15, 0.25, 0.35, 0.47, 0.58, 0.70, 0.82, 0.94],   // score needed for faces 2 to 9
  };

  const TIERS = { 1: "Just a thought, dear", 2: "I'm just saying", 3: "Back in my day" };
  const LEVELS = { 1: "mild", 2: "medium", 3: "spicy" };

  /* One Grandma per step. `name` is the data-face value in the markup. */
  const FACES = [
    { name: "furious",   say: "Pick a demand, dear. I'm waiting." },   // no demand picked yet
    { name: "asleep",    say: "Zzz... wake me when it's good." },
    { name: "sideeye",   say: "Hmph. Fine." },
    { name: "eyeroll",   say: "Is that all, dear?" },
    { name: "smug",      say: "Not bad, dear." },
    { name: "pleased",   say: "Now we're talking." },
    { name: "thumbsup",  say: "Very nice." },
    { name: "approved",  say: "Approved!" },
    { name: "confetti",  say: "Marvelous!" },
    { name: "overjoyed", say: "You darling!" },
  ];

  /* ---------- the maths (pure functions, no page needed) ---------- */

  const multiplier = (x) => {
    const { cap, k, xmax } = CONFIG;
    return k === 0
      ? 1 + (cap - 1) * (x / xmax)
      : 1 + ((cap - 1) * (1 - Math.exp(-k * x))) / (1 - Math.exp(-k * xmax));
  };

  /* input: { tiers: [0 to 3, ...up to 3], hours, quality: bool, ribbon: bool } */
  const xFor = ({ tiers = [], hours = 0, quality = false, ribbon = false }) => {
    const { tier, huge, hugeHours, xmax } = CONFIG;
    const demands = tiers.reduce((sum, t) => sum + (tier[t] || 0), 0);
    return Math.min(xmax, demands + (quality ? CONFIG.quality : 0) + (hours >= hugeHours ? huge : 0) + (ribbon ? CONFIG.ribbon : 0));
  };

  /* USD per hour. Internal only: it exists so the PDF table can be checked, never show it. */
  const usdPerHour = (x) => CONFIG.base * multiplier(x);

  /* Cookies for the whole project (not rounded: round when you show it). */
  const cookies = (input) => usdPerHour(xFor(input)) * CONFIG.cookiesPerUsd * (input.hours || 0);

  /* Which Grandma (index into FACES). Furious only while no demand is picked. */
  const face = (input) => {
    const { demandWeight, hoursWeight, faceAt, xmax } = CONFIG;
    if (!(input.tiers || []).some(Boolean)) return 0;
    const hoursMax = input.hoursMax || CONFIG.hoursMax;
    const demandPart = xFor(input) / xmax;
    const hoursPart = Math.min(1, Math.max(0, ((input.hours || 0) - 1) / (hoursMax - 1)));
    const score = demandWeight * demandPart + hoursWeight * hoursPart;
    let f = 1;
    faceAt.forEach((t, i) => { if (score >= t) f = i + 2; });
    return f;
  };

  /* ---------- the page wiring ---------- */

  /* Markup contract (all inside one root element):
       [data-pay="slot"] x3        demand notes, tap to cycle mild / medium / spicy / none
       [data-pay="hours"]          <input type="range">
       [data-pay="hours-out"]      shows the hours
       [data-pay="total"]          shows the cookies
       [data-pay="say"]            Grandma's one-liner
       [data-pay="huge"]           lights up by itself at 20 hours and up
       [data-pay="quality"] and [data-pay="ribbon"]    toggle buttons (aria-pressed)
       [data-face="furious" ... "overjoyed"]           one figure per face, only one is shown
     Fires a "pay:change" event on the root with { x, cookies, face, hours }. */
  const mount = (rootEl, opts = {}) => {
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

    const reduce = opts.reduceMotion !== undefined ? opts.reduceMotion : matchMedia("(prefers-reduced-motion: reduce)").matches;
    const g = opts.gsap !== undefined ? opts.gsap : (typeof gsap !== "undefined" ? gsap : null);
    const animate = !!g && !reduce;

    const tiers = [0, 0, 0];
    const flag = { quality: false, ribbon: false };
    const shown = { cookies: 0, face: -1 };
    const state = () => ({ tiers: [...tiers], hours: Number(hoursEl.value), quality: flag.quality, ribbon: flag.ribbon, hoursMax: Number(hoursEl.max) || CONFIG.hoursMax });

    const text = (tag, t) => { const e = document.createElement(tag); e.textContent = t; return e; };
    const showCookies = (n) => { totalEl.textContent = Math.round(n).toLocaleString(); };

    const update = (first) => {
      const s = state();
      const x = xFor(s);
      const total = cookies(s);
      const f = face(s);
      hoursOut.textContent = s.hours;
      hugeEl.setAttribute("aria-pressed", String(s.hours >= CONFIG.hugeHours));

      if (animate && !first) {
        g.to(shown, { cookies: total, duration: 0.35, ease: "steps(6)", overwrite: true, onUpdate: () => showCookies(shown.cookies) });
      } else {
        shown.cookies = total;
        showCookies(total);
      }

      FACES.forEach((def, i) => { if (figs[def.name]) figs[def.name].hidden = i !== f; });
      sayEl.textContent = FACES[f].say;
      if (animate && !first && f !== shown.face && figs[FACES[f].name]) {
        g.fromTo(figs[FACES[f].name], { scale: 0.92 }, { scale: 1, duration: 0.3, ease: "steps(3)", transformOrigin: "50% 100%" });
      }
      shown.face = f;
      rootEl.dispatchEvent(new CustomEvent("pay:change", { detail: { x, cookies: total, face: f, hours: s.hours } }));
    };

    /* tap a note: mild, medium, spicy, then clear. The next note appears once this one is filled. */
    const defaults = [["Add a demand", "tap me"], ["Another one?", "optional"], ["One more?", "if you dare"]];
    const paintSlots = () => {
      slots.forEach((s, i) => {
        s.hidden = i > 0 && !tiers[i - 1];
        const t = tiers[i];
        s.toggleAttribute("data-tier", !!t);
        if (t) s.dataset.tier = t;
        s.replaceChildren(text("b", t ? TIERS[t] : defaults[i][0]), text("span", t ? LEVELS[t] : defaults[i][1]));
      });
    };
    slots.forEach((s, i) => s.addEventListener("click", () => {
      tiers[i] = (tiers[i] + 1) % 4;
      if (!tiers[i]) tiers.fill(0, i + 1);     // clearing a note clears the ones after it
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
  };

  return { CONFIG, TIERS, LEVELS, FACES, multiplier, xFor, usdPerHour, cookies, face, mount };
});
