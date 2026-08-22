// @vitest-environment jsdom
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {App as AntApp, Button, ConfigProvider, theme} from 'antd';
import {darkTheme, lightTheme} from '../theme';

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});
afterEach(cleanup);

function ConfirmTrigger() {
  const {modal} = AntApp.useApp();
  const {token} = theme.useToken();
  return <Button onClick={() => modal.confirm({
    title: 'Проверка темы',
    content: <span data-testid="theme-token" data-bg={token.colorBgElevated}>Содержимое</span>,
  })}>Открыть</Button>;
}

function renderConfirmation(dark: boolean) {
  render(
    <ConfigProvider theme={dark ? darkTheme : lightTheme}>
      <AntApp><ConfirmTrigger/></AntApp>
    </ConfigProvider>,
  );
  fireEvent.click(screen.getByRole('button', {name: 'Открыть'}));
  return screen.getByTestId('theme-token').getAttribute('data-bg');
}

describe('contextual confirmation theme', () => {
  it('inherits different elevated background tokens in light and dark themes', () => {
    const lightBackground = renderConfirmation(false);
    cleanup();
    const darkBackground = renderConfirmation(true);

    expect(lightBackground).toBeTruthy();
    expect(darkBackground).toBeTruthy();
    expect(darkBackground).not.toBe(lightBackground);
    expect(screen.getByRole('dialog', {name: 'Проверка темы'})).toBeTruthy();
  });
});
