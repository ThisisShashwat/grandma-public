import { $$ } from "./dom.js";

/* Once the page has loaded and the browser is idle, fetch (and decode) the pictures the page may show next, so they are already there:
   Grandma's faces first (the calculator swaps them as the numbers change, and they are lazy and hidden, so the browser would never fetch them by itself),
   then every other lazy picture of this page. Nothing on a slow or data saving connection, never more than three at a time, no other page's pictures. */
const AT_A_TIME = 3;

const frugal = () => {
  const c = navigator.connection;
  return !!c && (c.saveData || ["slow-2g", "2g"].includes(c.effectiveType));
};

const fetchOne = (img) => {
  img.loading = "eager";               // a lazy picture starts loading now
  return img.decode().catch(() => {});  // resolves when it is loaded and decoded; a broken one is art.js's business
};

const lane = async (queue) => {
  for (let img; (img = queue.shift());) await fetchOne(img);
};

export function initPreload() {
  if (frugal()) return;
  const run = () => {
    const queue = [...new Set([...$$("[data-face] img"), ...$$('img[loading="lazy"]')])];
    for (let i = 0; i < AT_A_TIME; i++) lane(queue);
  };
  const idle = () => ("requestIdleCallback" in window ? requestIdleCallback(run) : setTimeout(run, 1500));
  if (document.readyState === "complete") idle();
  else addEventListener("load", idle, { once: true });
}
