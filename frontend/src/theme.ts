import {theme as antdTheme, type ThemeConfig} from 'antd';

// Semantic colors follow Ant Design's palette; neutral dark surfaces mirror the
// regular (non-ultra) dark mode from 3x-ui.
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
    colorBgBase: '#1a1b1f',
    colorBgContainer: '#23252b',
    colorBgElevated: '#2d2f37',
    colorBgLayout: '#1a1b1f',
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
  dark: {bg: '#15161a', text: '#F7F9FCA3'},
  light: {bg: '#F5F7FA', text: '#10151FA3'},
};
