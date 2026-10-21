/* What the browser and the page URL allow. Every library is optional: if one fails to load, the rest still works. */
export const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
export const finePointer = matchMedia("(pointer: fine)").matches;
export const hasGsap = typeof gsap !== "undefined";
export const hasScroll = typeof ScrollTrigger !== "undefined";
export const hasDrag = typeof Draggable !== "undefined";

if (hasGsap && hasScroll) gsap.registerPlugin(ScrollTrigger);
if (hasGsap && hasDrag) gsap.registerPlugin(Draggable);
