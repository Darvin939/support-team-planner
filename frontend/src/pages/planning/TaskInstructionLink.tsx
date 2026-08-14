import type {MouseEvent} from 'react';

export function TaskInstructionLink({url}: {url: string | null}) {
  if (!url) return null;

  const stopRowAction = (event: MouseEvent<HTMLAnchorElement>) => {
    event.stopPropagation();
  };

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={stopRowAction}
      onContextMenu={stopRowAction}
      style={{display: 'inline-block', marginTop: 3, fontSize: '0.75rem'}}
    >
      Инструкция ↗
    </a>
  );
}
