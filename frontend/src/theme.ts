import {theme as antdTheme, type ThemeConfig} from 'antd';

// Color values are Ant Design's own official palette (@ant-design/colors v8.0.1
// blue/gold/red/green + their dedicated *Dark variants) - not hand-picked, so the
// dark theme doesn't just look like the light theme boosted brighter.
const shared = {
  borderRadius: 9,
  borderRadiusSM: 6,
  fontFamily: "'InterVariable', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
};

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    ...shared,
    colorPrimary: '#1668dc',
    colorSuccess: '#49aa19',
    colorWarning: '#d89614',
    colorError: '#d32029',
    colorInfo: '#1668dc',
    colorBgBase: '#0B0F16',
    colorBgContainer: '#131A24',
    colorBgElevated: '#1B2430',
    colorBgLayout: '#0B0F16',
  },
};

export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    ...shared,
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#f5222d',
    colorInfo: '#1677ff',
    colorBgLayout: '#EEF1F6',
  },
};

// Sidebar ("chrome") stays a distinct dark panel in both themes in the current
// vanilla-JS app; mirrored here for the AppShell rather than left to antd's Sider defaults.
export const chrome = {
  dark: {bg: '#0A0E14', text: '#F7F9FCA3'},
  light: {bg: '#F5F7FA', text: '#10151FA3'},
};
