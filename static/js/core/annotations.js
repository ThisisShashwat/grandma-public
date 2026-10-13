import { $$, debounce } from "./dom.js";
import { reduce, hasGsap, hasScroll } from "./env.js";

/* Hand-drawn marks (Rough Notation) on every [data-annotate="highlight|underline|circle|strike-through"], colored by data-color.
   A strike-through gets a thinner pen (2): a crossed-off X hid letters, and both the struck words and the red fix beside them must stay readable.

   Rough Notation draws each mark once at the spot the text was at. When the window resizes and the text re-wraps,
   a mark can end up on the wrong words (the library only notices size changes, not moves, and cannot see inline
   text at all). So every mark is torn down and redrawn, without the animation, whenever the layout can have
   changed: resize, fonts, images, and a FAQ item opening (closed items have no layout). */
const marks = [];

/* A mark draws once it is 85% of the way up the screen. One near the very end of a page (the footer's) never gets that far,
   so its start is capped at the last scroll position instead of staying unreachable and never drawing. */
const drawAt = (node) => () => Math.min(
  node.getBoundingClientRect().top + scrollY - innerHeight * 0.85,
  ScrollTrigger.maxScroll(window) - 1,
);

const redraw = (m, animate) => {
  if (!m.node.getClientRects().length) return;          // hidden, for example inside a closed FAQ item
  m.mark.hide();
  m.mark.animate = animate && !reduce;
  m.mark.show();
  m.mark.animate = !reduce;
  m.wanted = true;
};
const redrawAll = () => marks.forEach((m) => { if (m.wanted) redraw(m, false); });

const setup = () => {
  if (typeof RoughNotation === "undefined") return;
  $$("[data-annotate]").forEach((node) => {
    const mark = RoughNotation.annotate(node, {
      type: node.dataset.annotate,
      color: node.dataset.color || "#000",
      strokeWidth: node.dataset.annotate === "strike-through" ? 2 : 3,
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
      ScrollTrigger.create({ trigger: node, start: drawAt(node), once: true, onEnter: () => redraw(m, true) });
    } else {
      redraw(m, true);
    }
  });
  addEventListener("resize", debounce(redrawAll, 150));
  addEventListener("load", () => setTimeout(redrawAll, 100));
  if ("ResizeObserver" in window) new ResizeObserver(debounce(redrawAll, 150)).observe(document.body);
};

/* wait for the fonts so the marks line up with the final text */
export function initAnnotations() {
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(setup);
  else setup();
}
