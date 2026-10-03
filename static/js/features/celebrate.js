import { $$ } from "../core/dom.js";
import { reduce } from "../core/env.js";
import { burst } from "../core/confetti.js";

/* A Blue Ribbon: the figure marked [data-celebrate] pops in (CSS, talk.css) and confetti goes off from it, once, as the page opens.
   Nothing happens for people who asked for less motion. */
export function celebrate() {
  if (reduce) return;
  $$("[data-celebrate]").forEach((fig) => {
    const r = fig.getBoundingClientRect();
    burst({ x: (r.left + r.width / 2) / innerWidth, y: (r.top + r.height / 3) / innerHeight }, true);
  });
}
