import type {CSSProperties, ReactNode} from 'react';
import {theme} from 'antd';

/**
 * Shared filter-row container: flex-wrap on desktop (unchanged), a CSS grid on mobile
 * so narrow fields (search/selects) can share a row instead of each forcing its own
 * full-width line. Used identically by every page with a filter row, so mobile
 * behavior doesn't silently diverge between pages.
 */
export function FilterGrid({ isMobile, children }: { isMobile: boolean; children: ReactNode }) {
  const style: CSSProperties = isMobile
    ? { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12, width: '100%' }
    : { display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' };
  return <div style={style}>{children}</div>;
}

/**
 * A single filter field: optional small uppercase caption above the control.
 * `mobileSpan` lets a field claim more than one grid column on mobile (e.g. a date
 * range picker needs more room than a plain select) or the full row (`'full'`).
 * The caption is forced to a single line (ellipsis instead of wrapping) — a wrapped
 * two-line caption throws off row height and misaligns neighboring fields in the
 * same grid row.
 */
export function FilterField({
  label,
  isMobile,
  mobileSpan,
  children,
}: {
  label?: string;
  isMobile: boolean;
  mobileSpan?: number | 'full';
  children: ReactNode;
}) {
  const { token } = theme.useToken();
  return (
    <div style={isMobile && mobileSpan ? { gridColumn: mobileSpan === 'full' ? '1 / -1' : `span ${mobileSpan}`, minWidth: 0 } : { minWidth: 0 }}>
      {label && (
        <div
          title={label}
          style={{
            fontSize: '0.8rem',
            color: token.colorTextTertiary,
            marginBottom: 4,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {label}
        </div>
      )}
      {children}
    </div>
  );
}
