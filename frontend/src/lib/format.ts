export interface RussianNounForms {
  one: string;
  few: string;
  many: string;
}

/** Formats a count with the supplied Russian singular, paucal, and plural noun forms. */
export function formatRussianCount(count: number, forms: RussianNounForms): string {
  const absoluteCount = Math.abs(count);
  const lastTwoDigits = absoluteCount % 100;
  const lastDigit = absoluteCount % 10;
  const noun = lastTwoDigits >= 11 && lastTwoDigits <= 14
    ? forms.many
    : lastDigit === 1
      ? forms.one
      : lastDigit >= 2 && lastDigit <= 4
        ? forms.few
        : forms.many;
  return `${count} ${noun}`;
}
