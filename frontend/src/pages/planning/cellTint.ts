import type {GlobalToken} from 'antd/es/theme/interface';

interface CellTintFlags {
  isToday: boolean;
  isFreeze: boolean;
  isWeekend: boolean;
}

function stripe(base: string, accent: string): string {
  return `repeating-linear-gradient(45deg, ${base}, ${base} 5px, ${accent} 5px, ${accent} 10px)`;
}

/**
 * Port of the original planning.js/style.css `.schedule-cell` state precedence
 * (today/freeze/weekend), including the diagonal-stripe freeze pattern. Freeze
 * days use a repeating-linear-gradient rather than a flat tint so a frozen day
 * is visually distinct from a plain colored day at a glance, same as the
 * vanilla-JS version. `current.freeze` in the original ignores weekend (no
 * `.current.freeze.weekend` rule existed), so this mirrors that exactly.
 */
export function getCellTint(token: GlobalToken, { isToday, isFreeze, isWeekend }: CellTintFlags): { background?: string; backgroundImage?: string } {
  const errorStripeAccent = `color-mix(in srgb, ${token.colorError} 8%, transparent)`;
  const warningStripeBase = `color-mix(in srgb, ${token.colorWarning} 5%, transparent)`;

  if (isToday && isFreeze) {
    return { backgroundImage: stripe('transparent', errorStripeAccent) };
  }
  if (isToday && isWeekend) {
    return { background: `color-mix(in srgb, ${token.colorWarning} 8%, transparent)` };
  }
  if (isToday) {
    return { background: `color-mix(in srgb, ${token.colorPrimary} 6%, transparent)` };
  }
  if (isFreeze && isWeekend) {
    return { backgroundImage: stripe(warningStripeBase, errorStripeAccent) };
  }
  if (isFreeze) {
    return { backgroundImage: stripe('transparent', errorStripeAccent) };
  }
  if (isWeekend) {
    return { background: `color-mix(in srgb, ${token.colorWarning} 6%, transparent)` };
  }
  return {};
}
