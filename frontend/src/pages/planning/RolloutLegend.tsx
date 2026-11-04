import {useState} from 'react';
import {Button, Popover, theme} from 'antd';
import {CloseOutlined, InfoCircleOutlined} from '@ant-design/icons';
import type {BlockTemplate, Task} from '../../domain/types';
import {formatRolloutShift, groupRolloutBlocks} from './rolloutLegendStages';

export interface RolloutTemplatesState {
  data?: BlockTemplate[];
  isLoading: boolean;
  isError: boolean;
}

export function RolloutLegend({task, templates}: {task: Task; templates: RolloutTemplatesState}) {
  const {token} = theme.useToken();
  const [open, setOpen] = useState(false);
  const template = templates.data?.find((item) => item.id === task.completion_template_id
    && item.segment_id === task.segment_id);
  const reason = !task.completion_template_id ? 'Шаблон раскатки не указан в работе'
    : templates.isLoading ? 'Загрузка шаблона раскатки…'
      : templates.isError ? 'Не удалось загрузить шаблон раскатки'
        : !template ? 'Шаблон работы недоступен команде или не соответствует сегменту' : null;
  const title = `Схема раскатки: ${task.name}`;
  const content = (
    <section aria-label={title} data-rollout-legend
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {event.stopPropagation(); setOpen(false);}
      }}
      style={{width: 'min(320px, calc(100vw - 64px))', maxHeight: 'min(480px, 40dvh)',
        overflowY: 'auto', overflowWrap: 'anywhere'}}>
      <div style={{position: 'sticky', top: 0, background: token.colorBgElevated,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8}}>
        <span style={{fontWeight: token.fontWeightStrong}}>Схема раскатки</span>
        <Button type="text" size="small" htmlType="button" disabled={false}
          aria-label="Закрыть схему раскатки" icon={<CloseOutlined/>} onClick={() => setOpen(false)}/>
      </div>
      {reason ? <div role="status">{reason}</div> : template && <>
        <div style={{fontWeight: token.fontWeightStrong, marginBottom: 12}}>{template.name}</div>
        {template.blocks.length === 0 ? <div>В шаблоне нет блоков</div> : <ol
          style={{listStyle: 'none', padding: 0, margin: 0}}>
          {groupRolloutBlocks(template.blocks).map(({shift, blocks}, index) => <li key={shift}>
            {index > 0 && <div aria-hidden="true" style={{color: token.colorTextTertiary, margin: '4px 0'}}>↓</div>}
            <div style={{display: 'grid', gridTemplateColumns: '84px minmax(0, 1fr)', gap: 12}}>
              <span style={{color: token.colorTextSecondary}}>{formatRolloutShift(shift)}</span>
              <div>{blocks.map((block) => block.name).join(', ')}</div>
            </div>
          </li>)}
        </ol>}
        <div style={{marginTop: 12, fontSize: token.fontSizeSM, color: token.colorTextSecondary}}>
          <div>Сдвиги относительно начала раскатки</div>
          <div>Даты при ручном планировании выбираются отдельно</div>
        </div>
      </>}
    </section>
  );
  return <Popover trigger="click" open={open} onOpenChange={setOpen} content={content}
    placement="bottom" destroyOnHidden>
    <Button type="text" size="small" htmlType="button" disabled={false}
      aria-label={title} aria-expanded={open} title="Схема раскатки"
      icon={<InfoCircleOutlined/>} style={{flexShrink: 0, color: token.colorTextSecondary}}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === 'Escape') setOpen(false);
      }}/>
  </Popover>;
}
