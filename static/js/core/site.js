/* Runs on every page (loaded by templates/base.html): the things every page has. */
import { data } from "./data.js";
import { initArt } from "./art.js";
import { initCountdown } from "./countdown.js";
import { initConfetti } from "./confetti.js";
import { initAnnotations } from "./annotations.js";
import { initDev } from "./dev.js";
import { initPreload } from "./preload.js";

initArt();
initCountdown(data.launch);
initConfetti();
initAnnotations();
initDev();
initPreload();
