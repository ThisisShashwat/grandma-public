/* Any page that runs a dialogue (templates/pages/talk.html). */
import { prefillHints } from "../features/talk.js";
import { celebrate } from "../features/celebrate.js";

prefillHints();
celebrate();
