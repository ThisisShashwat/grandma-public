/* Grandma's payout maths, browser twin of program/payout.py (which holds the constants and the frozen formula).
   Pure functions, no page needed: `config` is payout.CONFIG as JSON (data.pay).
     const pay = createPay(data.pay);
     pay.cookies({ tiers: [2, 3], hours: 24, quality: true, ribbon: false })   // cookies for those hours
     (ribbonHolder: true earns the same config.ribbon term as ribbon: true, for holding a Blue Ribbon from an earlier project; counted once, never stacked)
     pay.face({ tiers: [2, 3], hours: 24, quality: true })                     // 0 to 9, index into the faces list
   Dollars are internal only: never show usdPerHour. */
export function createPay(config) {
  const multiplier = (x) => {
    const { cap, k, xmax } = config;
    return 1 + ((cap - 1) * (1 - Math.exp(-k * x))) / (1 - Math.exp(-k * xmax));
  };

  /* input: { tiers: [0 to 3, ...up to 3], hours, quality: bool, ribbon: bool, ribbonHolder: bool } */
  const xFor = ({ tiers = [], hours = 0, quality = false, ribbon = false, ribbonHolder = false }) => {
    const { tier, huge, hugeHours, xmax } = config;
    const demands = tiers.reduce((sum, t) => sum + (tier[t] || 0), 0);
    return Math.min(xmax, demands + (quality ? config.quality : 0) + (hours >= hugeHours ? huge : 0) + (ribbon || ribbonHolder ? config.ribbon : 0));
  };

  const usdPerHour = (x) => config.base * multiplier(x);

  /* cookies for the whole project, not rounded: round when you show it */
  const cookies = (input) => usdPerHour(xFor(input)) * config.cookiesPerUsd * (input.hours || 0);

  /* which Grandma (0 to 9). Furious only while no demand is picked. */
  const face = (input) => {
    const { demandWeight, hoursWeight, faceAt, xmax } = config;
    if (!(input.tiers || []).some(Boolean)) return 0;
    const hoursMax = input.hoursMax || config.hoursMax;
    const demandPart = xFor(input) / xmax;
    const hoursPart = Math.min(1, Math.max(0, ((input.hours || 0) - 1) / (hoursMax - 1)));
    const score = demandWeight * demandPart + hoursWeight * hoursPart;
    let f = 1;
    faceAt.forEach((t, i) => { if (score >= t) f = i + 2; });
    return f;
  };

  return { config, multiplier, xFor, usdPerHour, cookies, face };
}
