// @vitest-environment jsdom
import {cleanup, fireEvent, render, waitFor} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import App from './App';

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe('theme preference', () => {
  it('keeps the existing two-mode theme value in localStorage', async () => {
    localStorage.setItem('theme', 'light');
    window.history.replaceState({}, '', '/login');
    const {container} = render(<App/>);

    const toggle = await waitFor(() => {
      const button = container.querySelector<HTMLButtonElement>('button[aria-label]');
      expect(button).toBeTruthy();
      return button as HTMLButtonElement;
    });

    fireEvent.click(toggle);
    await waitFor(() => expect(localStorage.getItem('theme')).toBe(''));

    fireEvent.click(toggle);
    await waitFor(() => expect(localStorage.getItem('theme')).toBe('light'));
  });
});
