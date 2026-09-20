import type {CSSProperties, ReactNode} from 'react';
import {theme} from 'antd';
import dayjs from 'dayjs';
import {DISPLAY_DATE_SHORT_FORMAT} from '../../lib/dateFormats';
import {usePlanningGridDragScroll} from './usePlanningGridDragScroll';

export interface PlanningDateGridProps {
  dates: string[];
  firstColumnHeader: ReactNode;
  firstColumnBody: ReactNode;
  renderDateHeader?: (date: string, index: number) => ReactNode;
  renderDateCell: (date: string) => ReactNode;
  getDateHeaderStyle?: (date: string, index: number) => CSSProperties;
  getDateCellStyle?: (date: string) => CSSProperties;
  fontSize?: number | string;
  dataAttribute?: string;
}

export function PlanningDateGridFrame({scrollRef, children, dataAttribute = 'data-planning-date-grid'}: {
  scrollRef: {current: HTMLDivElement | null};
  children: ReactNode;
  dataAttribute?: string;
}) {
  const {token} = theme.useToken();
  return <div ref={scrollRef} data-planning-grid-scroll={dataAttribute} style={{display: 'block', overflowX: 'auto', width: 0, minWidth: '100%', maxWidth: '100%', boxSizing: 'border-box', border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadiusSM}}>{children}</div>;
}

export function PlanningDateGrid({
  dates,
  firstColumnHeader,
  firstColumnBody,
  renderDateHeader,
  renderDateCell,
  getDateHeaderStyle,
  getDateCellStyle,
  fontSize,
  dataAttribute = 'data-planning-date-grid',
}: PlanningDateGridProps) {
  const {token} = theme.useToken();
  const dragRef = usePlanningGridDragScroll<HTMLDivElement>();
  const border = `1px solid ${token.colorBorderSecondary}`;
  const fixedColumn: CSSProperties = {
    position: 'sticky',
    left: 0,
    borderRight: border,
  };
  const headerBase: CSSProperties = {
    position: 'relative',
    padding: `${token.paddingXS}px`,
    textAlign: 'left',
    color: token.colorTextHeading,
    fontWeight: token.fontWeightStrong,
    background: token.colorFillAlter,
    borderBottom: border,
  };
  const bodyBase: CSSProperties = {
    padding: `${token.paddingXS}px`,
    borderBottom: border,
    verticalAlign: 'top',
  };
  const stickyHeaderBackground = `linear-gradient(${token.colorFillAlter}, ${token.colorFillAlter}), linear-gradient(${token.colorBgContainer}, ${token.colorBgContainer})`;

  return (
    <div ref={dragRef} data-planning-grid-scroll={dataAttribute} style={{display: 'block', overflowX: 'auto', width: 0, minWidth: '100%', maxWidth: '100%', boxSizing: 'border-box', border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadiusSM}}>
      <table style={{borderCollapse: 'collapse', width: 'max-content', minWidth: '100%', fontSize: fontSize ?? token.fontSize}}>
        <thead>
          <tr>
            <th style={{...headerBase, ...fixedColumn, zIndex: 2, background: undefined, backgroundImage: stickyHeaderBackground}}>{firstColumnHeader}</th>
            {dates.map((date, index) => (
              <th key={date} style={{...headerBase, ...getDateHeaderStyle?.(date, index)}}>
                {renderDateHeader ? renderDateHeader(date, index) : dayjs(date).format(DISPLAY_DATE_SHORT_FORMAT)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th style={{...bodyBase, ...fixedColumn, zIndex: 1, background: token.colorBgContainer, fontWeight: token.fontWeightStrong, textAlign: 'left'}}>{firstColumnBody}</th>
            {dates.map((date) => <td key={date} style={{...bodyBase, ...getDateCellStyle?.(date)}}>{renderDateCell(date)}</td>)}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
