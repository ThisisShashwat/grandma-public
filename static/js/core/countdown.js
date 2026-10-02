import { $$ } from "./dom.js";

const pad = (n) => String(n).padStart(2, "0");

/* Any [data-cd] element shows "Grandma calls in N days HH:MM:SS", or "Grandma is calling now". */
export function initCountdown(launch) {
  const launchAt = new Date(launch).getTime();
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
}
