// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {TaskInstructionLink} from './TaskInstructionLink';

afterEach(cleanup);

describe('TaskInstructionLink', () => {
  it('does not render without a URL', () => {
    const {container} = render(<TaskInstructionLink url={null}/>);

    expect(container.innerHTML).toBe('');
  });

  it('renders a safe external link without triggering row actions', () => {
    const onClick = vi.fn();
    const onContextMenu = vi.fn();
    render(
      <div onClick={onClick} onContextMenu={onContextMenu}>
        <TaskInstructionLink url="https://docs.example.test/task"/>
      </div>,
    );

    const link = screen.getByRole('link', {name: 'Инструкция ↗'});
    expect(link.getAttribute('href')).toBe('https://docs.example.test/task');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');

    fireEvent.click(link);
    fireEvent.contextMenu(link);

    expect(onClick).not.toHaveBeenCalled();
    expect(onContextMenu).not.toHaveBeenCalled();
  });
});
