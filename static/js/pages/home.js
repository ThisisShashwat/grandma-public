/* Home page behaviour (loaded by templates/pages/home.html, after core/site.js). */
import { $ } from "../core/dom.js";
import { data } from "../core/data.js";
import { heroMotion, phoneShake } from "../features/motion.js";
import { initFridge } from "../features/fridge.js";
import { createPay } from "../modules/pay/math.js";
import { mount } from "../modules/pay/widget.js";

heroMotion();
initFridge(data);
mount($("[data-pay-root]"), { pay: createPay(data.pay), faces: data.faces, tiers: data.tiers, levels: data.levels });
phoneShake();
