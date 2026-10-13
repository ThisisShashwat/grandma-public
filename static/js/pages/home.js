/* Home page behaviour (loaded by templates/pages/home.html, after core/site.js). */
import { data } from "../core/data.js";
import { heroMotion, phoneShake } from "../features/motion.js";
import { initFridge } from "../features/fridge.js";

heroMotion();
initFridge(data);
phoneShake();
