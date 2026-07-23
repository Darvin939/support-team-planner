import {useState} from 'react';
import {DeleteOutlined, EditOutlined} from '@ant-design/icons';
import {Button, Card, Empty, message, Modal, Popconfirm, Select, Space, theme} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {useFreezeDays} from '../../hooks/useSettingsData';
import {apiMutate} from '../../lib/apiMutate';
import {queryKeys} from '../../lib/queryKeys';
import {invalidateSettingsData} from '../../lib/queryInvalidation';

const MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
const WEEKDAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const CURRENT_YEAR = new Date().getFullYear();

function getFreezeDaysByMonth(allDays: string[] | undefined): Map<number, Set<number>> {
  const byMonth = new Map<number, Set<number>>();
  const prefix = String(CURRENT_YEAR);
  (allDays ?? []).forEach((dateStr) => {
    if (!dateStr.startsWith(prefix)) return;
    const month = parseInt(dateStr.substring(5, 7), 10);
    const day = parseInt(dateStr.substring(8, 10), 10);
    if (!byMonth.has(month)) byMonth.set(month, new Set());
    byMonth.get(month)!.add(day);
  });
  return byMonth;
}

function MonthCalendarGrid({
                             month,
                             markedDays,
                             interactive,
                             onToggleDay,
                           }: {
  month: number;
  markedDays: Set<number>;
  interactive: boolean;
  onToggleDay?: (day: number) => void;
}) {
  const {token} = theme.useToken();
  const daysInMonth = new Date(CURRENT_YEAR, month, 0).getDate();
  let firstDow = new Date(CURRENT_YEAR, month - 1, 1).getDay();
  firstDow = firstDow === 0 ? 6 : firstDow - 1;
  const today = new Date();

  const cells: (number | null)[] = [...Array(firstDow).fill(null), ...Array.from({length: daysInMonth}, (_, i) => i + 1)];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <table style={{width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'center'}}>
      <thead>
      <tr>
        {WEEKDAY_NAMES.map((d) => (
          <th key={d} style={{color: token.colorTextTertiary, fontWeight: 500, padding: 2}}>
            {d}
          </th>
        ))}
      </tr>
      </thead>
      <tbody>
      {Array.from({length: cells.length / 7}, (_, row) => (
        <tr key={row}>
          {cells.slice(row * 7, row * 7 + 7).map((day, col) => {
            if (day === null) return <td key={col}/>;
            const isWeekend = col === 5 || col === 6;
            const isToday = CURRENT_YEAR === today.getFullYear() && month === today.getMonth() + 1 && day === today.getDate();
            const isMarked = markedDays.has(day);
            return (
              <td
                key={col}
                onClick={interactive ? () => onToggleDay?.(day) : undefined}
                style={{
                  padding: '3px 1px',
                  background: isWeekend ? `color-mix(in srgb, ${token.colorWarning} 8%, transparent)` : undefined,
                  cursor: interactive ? 'pointer' : undefined,
                }}
              >
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      lineHeight: 1,
                      background: isMarked ? token.colorError : undefined,
                      color: isMarked ? '#fff' : undefined,
                      fontWeight: isMarked ? 600 : 400,
                      border: isToday && !isMarked ? `2px solid ${token.colorPrimary}` : undefined,
                    }}
                  >
                    {day}
                  </span>
              </td>
            );
          })}
        </tr>
      ))}
      </tbody>
    </table>
  );
}

export function FreezeDaysTab() {
  const {data: freezeDays} = useFreezeDays();
  const queryClient = useQueryClient();
  const [modalMonth, setModalMonth] = useState<number | null>(null);
  const [modalSelectedDays, setModalSelectedDays] = useState<Set<number>>(new Set());
  const [isNewMonth, setIsNewMonth] = useState(false);

  const byMonth = getFreezeDaysByMonth(freezeDays);
  const configuredMonths = [...byMonth.keys()].sort((a, b) => a - b);

  const saveMutation = useMutation({
    mutationFn: (days: number[]) => apiMutate('/api/freeze-days/month', 'PUT', {
      year: CURRENT_YEAR,
      month: modalMonth,
      days
    }),
    onSuccess: () => {
      invalidateSettingsData(queryClient, queryKeys.freezeDays);
      message.success('Сохранено');
      setModalMonth(null);
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (month: number) => apiMutate(`/api/freeze-days/month/${CURRENT_YEAR}/${month}`, 'DELETE'),
    onSuccess: () => {
      invalidateSettingsData(queryClient, queryKeys.freezeDays);
      message.success('Удалено');
    },
    onError: (e: Error) => message.error(e.message),
  });

  function openAddModal() {
    let defaultMonth = 1;
    for (let m = 1; m <= 12; m++) {
      if (!byMonth.has(m)) {
        defaultMonth = m;
        break;
      }
    }
    setIsNewMonth(true);
    setModalMonth(defaultMonth);
    setModalSelectedDays(new Set(byMonth.get(defaultMonth) ?? []));
  }

  function openEditModal(month: number) {
    setIsNewMonth(false);
    setModalMonth(month);
    setModalSelectedDays(new Set(byMonth.get(month) ?? []));
  }

  function toggleDay(day: number) {
    setModalSelectedDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
  }

  return (
    <>
      <Space style={{marginBottom: 16}}>
        <Button type="primary" onClick={openAddModal}>
          Добавить месяц
        </Button>
      </Space>

      {configuredMonths.length === 0 ? (
        <Empty description="Нет дней фриза"/>
      ) : (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14}}>
          {configuredMonths.map((m) => (
            <Card
              key={m}
              size="small"
              title={MONTH_NAMES[m - 1]}
              extra={
                <Space>
                  <Button size="small" onClick={() => openEditModal(m)}>
                    <EditOutlined/>
                  </Button>
                  <Popconfirm title={`Удалить все дни фриза за ${MONTH_NAMES[m - 1]}?`}
                              onConfirm={() => deleteMutation.mutate(m)} okText="Удалить" cancelText="Отмена">
                    <Button size="small" danger>
                      <DeleteOutlined/>
                    </Button>
                  </Popconfirm>
                </Space>
              }
            >
              <MonthCalendarGrid month={m} markedDays={byMonth.get(m) ?? new Set()} interactive={false}/>
            </Card>
          ))}
        </div>
      )}

      <Modal
        title={isNewMonth ? 'Добавить дни фриза' : `Редактирование: ${modalMonth ? MONTH_NAMES[modalMonth - 1] : ''}`}
        open={modalMonth !== null}
        onCancel={() => setModalMonth(null)}
        onOk={() => saveMutation.mutate([...modalSelectedDays].sort((a, b) => a - b))}
        okText="Сохранить"
        confirmLoading={saveMutation.isPending}
        width={350}
      >
        {isNewMonth && (
          <Select
            style={{width: '100%', marginBottom: 12}}
            value={modalMonth}
            onChange={(m) => {
              setModalMonth(m);
              setModalSelectedDays(new Set(byMonth.get(m) ?? []));
            }}
            options={MONTH_NAMES.map((name, i) => ({value: i + 1, label: name}))}
          />
        )}
        {modalMonth !== null &&
            <MonthCalendarGrid month={modalMonth} markedDays={modalSelectedDays} interactive onToggleDay={toggleDay}/>}
      </Modal>
    </>
  );
}
