/* Help Grandma Out: homepage behavior.
   Every library is optional: if one fails to load, the rest of the page still works. */

/* ============ CONFIG: edit these ============ */
const CONFIG = {
  launch: "2026-10-05T12:00:00Z",   // TODO: real launch moment (ISO, with timezone)
  links: {                          // empty string = shows a yellow TODO button
    signup: "",                     // your Fillout form or Submit link
    slack: "",
    repo: "",
    board: "",                      // where complaints (new demands) get sent
    rules: "",                      // fine print / HQ policies
    contact: "",                    // e.g. "mailto:you@example.com"
  },
  freeAsks: 3,
};

/* The 28 demands: [name, Grandma's line, tier 1 to 3] */
const POOL = [
  ["Tiny", "Everything I own fits in one cookie tin. So should this.", 2],
  ["One Button", "I only ever press the +30 seconds button on the microwave.", 2],
  ["Two Colors", "I only own two crayons. Use them wisely.", 1],
  ["Offline", "The internet is broken again, so it had better work without it.", 1],
  ["Big Print", "I can't read that tiny writing, dear. Make it big.", 1],
  ["No Jargon", "Explain it to me like I'm your grandmother. I am your grandmother.", 1],
  ["Audio Only", "Turn that screen off and tell me what's happening, dear.", 3],
  ["Homemade", "I don't trust anything I didn't bake myself.", 2],
  ["Single File", "I keep everything in one drawer, and I know exactly where.", 2],
  ["Plain Text", "If I can't open it in Notepad, I don't want it.", 1],
  ["Undo Everything", "Everybody makes mistakes, dear. Let me take that back.", 2],
  ["No Ifs", "In my day we didn't say 'if'. We just did it right.", 3],
  ["Homegrown Brain", "I don't trust a brain I didn't raise myself.", 3],
  ["URL State", "Everything you need is on the note. Don't lose the note.", 2],
  ["No JavaScript", "Back in my day a website was words and a picture, and we liked it.", 3],
  ["No Images", "Pictures cost money. Draw it with what you've got.", 2],
  ["One Screen", "One room, one game, no wandering off.", 1],
  ["Sixty Seconds", "Dinner's in a minute. Make it quick.", 1],
  ["Single Pin", "There's one free outlet and I'm not sharing.", 3],
  ["Battery Only", "The toaster has the only plug in the kitchen.", 1],
  ["No Soldering", "I lost the soldering iron and I'm not buying another.", 2],
  ["No Microcontroller", "Never trusted computers. Transistors only.", 3],
  ["Single-Sided PCB", "One side of the fabric only, dear. The other side is for show.", 2],
  ["Salvaged", "Waste not, want not. Take it out of the old radio in the attic.", 2],
  ["No Supports", "No scaffolding. I'm not building a cathedral.", 1],
  ["Snap-Fit", "Screws get lost in the couch. Make it click.", 2],
  ["Parametric", "Measure twice, and when I change my mind, change one number.", 2],
  ["Print-in-Place", "I don't do assembly. It arrives working or it goes back.", 3],
];
const TIERS = { 1: "Just a thought, dear", 2: "I'm just saying", 3: "Back in my day" };

/* classic MS Paint colors for the confetti */
const CONFETTI_COLORS = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#000000"];

/* ============ helpers ============ */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (tag, text, cls) => {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const shuffle = (a) => {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = matchMedia("(pointer: fine)").matches;
const dev = new URLSearchParams(location.search).has("dev");
const hasGsap = typeof gsap !== "undefined";
const hasScroll = typeof ScrollTrigger !== "undefined";
const hasDrag = typeof Draggable !== "undefined";

if (hasGsap && hasScroll) gsap.registerPlugin(ScrollTrigger);
if (hasGsap && hasDrag) gsap.registerPlugin(Draggable);

/* ============ links ============ */
// $$("[data-link]").forEach((a) => {
//   const url = CONFIG.links[a.dataset.link];
//   if (!url) {
//     a.href = "#todo-link";
//     a.classList.add("todo");
//     a.title = `TODO: set CONFIG.links.${a.dataset.link} in main.js`;
//     return;
//   }
//   a.href = url;
//   if (/^https?:/.test(url)) { a.target = "_blank"; a.rel = "noopener"; }
// });

/* ============ art placeholders ============
   A dashed box stays until the real image loads. Missing images just keep the box. */
$$(".fig img").forEach((img) => {
  const fig = img.closest(".fig");
  const done = () => fig.classList.remove("ph");
  img.addEventListener("load", done);
  img.addEventListener("error", () => img.remove());
  if (img.complete) { img.naturalWidth ? done() : img.remove(); }
});

/* ============ countdown ============ */
const launchAt = new Date(CONFIG.launch).getTime();
const pad = (n) => String(n).padStart(2, "0");
const tick = () => {
  const left = Math.floor((launchAt - Date.now()) / 1000);
  let text;
  if (left <= 0) {
    text = "Grandma is calling now";
  } else {
    const d = Math.floor(left / 86400);
    const r = left % 86400;
    text = `Grandma calls in ${d} ${d === 1 ? "day" : "days"} ${pad(Math.floor(r / 3600))}:${pad(Math.floor((r % 3600) / 60))}:${pad(r % 60)}`;
  }
  $$("[data-cd]").forEach((e) => { e.textContent = text; });
};
tick();
setInterval(tick, 1000);

/* ============ confetti on the sign-up buttons ============ */
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
      colors: CONFETTI_COLORS,
      origin: { x: (r.left + r.width / 2) / innerWidth, y: (r.top + r.height / 2) / innerHeight },
      disableForReducedMotion: true,
    });
  });
});

/* ============ hand-drawn marks (Rough Notation) ============
   Rough Notation draws each mark once at the spot the text was at. When the window resizes and the text
   re-wraps, a mark can end up on the wrong words (the library only notices size changes, not moves, and
   cannot see inline text at all). So every mark is torn down and redrawn, without the animation, whenever
   the layout can have changed: resize, fonts, images, and a FAQ item opening (closed items have no layout). */
const marks = [];
const redraw = (m, animate) => {
  if (!m.node.getClientRects().length) return;          // hidden, for example inside a closed FAQ item
  m.mark.hide();
  m.mark.animate = animate && !reduce;
  m.mark.show();
  m.mark.animate = !reduce;
  m.wanted = true;
};
const redrawAll = () => marks.forEach((m) => { if (m.wanted) redraw(m, false); });

const setupAnnotations = () => {
  if (typeof RoughNotation === "undefined") return;
  $$("[data-annotate]").forEach((node) => {
    const mark = RoughNotation.annotate(node, {
      type: node.dataset.annotate,
      color: node.dataset.color || "#000",
      strokeWidth: 3,
      padding: 4,
      multiline: true,
      animate: !reduce,
      animationDuration: 700,
    });
    const m = { node, mark, wanted: false };
    marks.push(m);
    const details = node.closest("details");
    if (details) {
      details.addEventListener("toggle", () => { if (details.open) requestAnimationFrame(() => redraw(m, true)); });
    } else if (hasGsap && hasScroll) {
      ScrollTrigger.create({ trigger: node, start: "top 85%", once: true, onEnter: () => redraw(m, true) });
    } else {
      redraw(m, true);
    }
  });
  addEventListener("resize", debounce(redrawAll, 150));
  addEventListener("load", () => setTimeout(redrawAll, 100));
  if ("ResizeObserver" in window) new ResizeObserver(debounce(redrawAll, 150)).observe(document.body);
};
/* wait for the fonts so the marks line up with the final text */
if (document.fonts && document.fonts.ready) document.fonts.ready.then(setupAnnotations);
else setupAnnotations();

/* ============ the one orchestrated moment: hero pop-in, then a wiggling spoon ============ */
if (hasGsap && !reduce && !dev) {
  gsap.from(".hero .fig", {
    scale: 0.5, rotation: -10, opacity: 0,
    duration: 0.6, ease: "steps(6)", stagger: 0.15, transformOrigin: "50% 100%",
  });
  gsap.to(".js-wiggle", {
    rotation: 2.5, duration: 0.45, repeat: -1, yoyo: true,
    ease: "steps(2)", transformOrigin: "50% 100%", delay: 1.4,
  });
}

/* ============ the fridge demo (the real draw happens on the server) ============ */
const fridge = $("#fridge");
const NOTE_COUNT = 6;
const notes = Array.from({ length: NOTE_COUNT }, () => {
  const n = document.createElement("div");
  n.className = "note";
  n.style.setProperty("--rot", (Math.random() * 6 - 3).toFixed(1));
  fridge.append(n);
  return n;
});

const deal = () => {
  shuffle([...POOL]).slice(0, NOTE_COUNT).forEach(([name, line, tier], i) => {
    notes[i].replaceChildren(el("b", name), line, el("span", TIERS[tier], "tier"));
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
const askFigs = $$(".ask-fig");                 // note pull, magnifier, eye roll, shocked, nose up
$("#ask").addEventListener("click", () => {
  asks++;
  const over = asks > CONFIG.freeAsks;
  const shownFig = Math.min(asks, askFigs.length - 1);
  askFigs.forEach((f, i) => { f.hidden = i !== shownFig; });
  if (hasGsap && !reduce) gsap.from(askFigs[shownFig], { scale: 0.85, rotation: -4, duration: 0.3, ease: "steps(3)" });
  $("#askStatus").textContent = over
    ? "That's enough, dear. In the real thing, more asks cost cookies."
    : `Ask ${asks} of ${CONFIG.freeAsks} free.`;
  deal();
});

/* ============ cookie calculator: all of it lives in pay.js so other pages can reuse it ============ */
if (typeof GrandmaPay !== "undefined") GrandmaPay.mount($("[data-pay-root]"));

/* hero for the Hack Club section: Grandma's phone shakes with outrage */
if (hasGsap && !reduce && !dev) {
  gsap.to(".js-phone", { rotation: -2, duration: 0.3, repeat: -1, yoyo: true, ease: "steps(2)", transformOrigin: "50% 100%" });
}

/* ============ dev mode: open the page with ?dev ============
   Drag art to place it, scroll over it to resize. Copy the numbers into the style attribute. */
if (dev && hasGsap && hasDrag) {
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
