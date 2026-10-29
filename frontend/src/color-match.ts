import { Color } from "@/src/api";

/** Best colour for the selected colour filter: solid colour first ("Svart"), then only-selected combos, then mixed ("Gul/Svart"). */
export function pickColor(colors: Color[] | undefined, selected: string[]): Color | undefined {
  if (!colors?.length || !selected.length) return undefined;
  let best: Color | undefined;
  let bestScore = -1;
  for (const c of colors) {
    const base = c.base ?? [];
    const hits = base.filter((b) => selected.includes(b)).length;
    if (!hits) continue;
    const only = base.every((b) => selected.includes(b));
    const solid = !c.name.includes("/");
    const score = solid && only ? 3 : solid ? 2 : only ? 1 : 0;
    if (score > bestScore) {
      best = c;
      bestScore = score;
    }
  }
  return best;
}
