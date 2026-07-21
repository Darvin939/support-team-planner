import {theme} from 'antd';

export function StatTile({label, value, accent, primary}: {
  label: string;
  value: number;
  accent?: string;
  primary?: boolean
}) {
  const {token} = theme.useToken();
  const color = accent ?? token.colorPrimary;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        minWidth: 84,
        padding: '7px 14px',
        borderRadius: token.borderRadius,
        border: `1px solid ${primary ? `color-mix(in srgb, ${color} 35%, ${token.colorBorder})` : token.colorBorder}`,
        background: primary ? `color-mix(in srgb, ${color} 10%, ${token.colorBgContainer})` : token.colorBgContainer,
      }}
    >
      <span style={{
        fontFamily: "'JetBrains Mono Variable', monospace",
        fontWeight: 700,
        fontSize: primary ? '1.3rem' : '1.15rem',
        lineHeight: 1.25,
        color
      }}>
        {value}
      </span>
      <span style={{
        fontSize: '0.68rem',
        color: primary ? color : token.colorTextSecondary,
        textTransform: 'uppercase',
        letterSpacing: '0.03em'
      }}>
        {label}
      </span>
    </div>
  );
}

export function StatGroupLabel({children}: { children: string }) {
  const {token} = theme.useToken();
  return (
    <span style={{
      fontWeight: 600,
      fontSize: '0.72rem',
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
      color: token.colorTextTertiary,
      alignSelf: 'center',
      margin: '0 2px'
    }}>
      {children}
    </span>
  );
}
