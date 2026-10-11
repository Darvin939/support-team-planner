import {describe, expect, it} from 'vitest';
import {chrome, darkTheme} from './theme';

describe('dark theme palette', () => {
  it('uses the regular 3x-ui dark surface levels', () => {
    expect(darkTheme.token).toMatchObject({
      colorBgBase: '#1a1b1f',
      colorBgLayout: '#1a1b1f',
      colorBgContainer: '#23252b',
      colorBgElevated: '#2d2f37',
    });
    expect(chrome.dark.bg).toBe('#15161a');
  });

  it('keeps the existing semantic colors', () => {
    expect(darkTheme.token).toMatchObject({
      colorPrimary: '#1668dc',
      colorSuccess: '#49aa19',
      colorWarning: '#d89614',
      colorError: '#d32029',
      colorInfo: '#1668dc',
    });
  });
});
