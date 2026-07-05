import type {ReactNode} from 'react';

const URL_PATTERN = /(https?:\/\/[^\s]+)/g;

/** Port of the original script.js linkify(): turns bare http(s) URLs in plain text into clickable links. */
export function linkify(text: string): ReactNode[] {
  const parts = text.split(URL_PATTERN);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <a key={i} href={part} target="_blank" rel="noreferrer">{part}</a>) : (part),
  );
}
