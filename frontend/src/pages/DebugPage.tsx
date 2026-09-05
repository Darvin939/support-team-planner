import {useEffect, useRef, useState} from 'react';
import {Button, Input, Select, Space, Typography} from 'antd';
import {Navigate} from 'react-router-dom';
import {useQuery} from '@tanstack/react-query';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {useMe} from '../hooks/useMe';
import {useDebouncedValue} from '../hooks/useDebouncedValue';

type LogRow = { timestamp: string; level: string; logger: string; message: string };

export function DebugPage() {
  const {data: me, isLoading} = useMe();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 500);
  const [level, setLevel] = useState('');
  const [follow, setFollow] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);
  const logs = useQuery({
    queryKey: ['debug-logs', debouncedSearch, level],
    queryFn: () => apiGet<{ rows: LogRow[] }>(buildApiUrl('/api/debug/logs', {
      limit: 500,
      search: debouncedSearch,
      level
    })),
    refetchInterval: 2000,
    enabled: me?.role === 'admin' && me.login === 'admin',
  });

  useEffect(() => {
    const node = logRef.current;
    if (node && follow && wasAtBottom.current) node.scrollTop = node.scrollHeight;
  }, [logs.data?.rows.length, follow]);

  if (!isLoading && (!me || me.role !== 'admin' || me.login !== 'admin')) return <Navigate to="/planning" replace/>;

  function onScroll() {
    const node = logRef.current;
    if (!node) return;
    wasAtBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 8;
    setFollow(wasAtBottom.current);
  }

  function jumpToEnd() {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
    wasAtBottom.current = true;
    setFollow(true);
  }

  return <div style={{padding: 24}}>
    <Typography.Title level={2}>Отладка</Typography.Title>
    <Typography.Title level={4}>Application log</Typography.Title>
    <Space orientation="vertical" style={{width: '100%'}}>
      <Space wrap>
        <Input placeholder="Поиск" value={search} onChange={(event) => setSearch(event.target.value)}
               style={{width: 280}}/>
        <Select aria-label="Уровень" allowClear placeholder="Уровень" style={{width: 150}} value={level || undefined}
                onChange={(value) => setLevel(value || '')}
                options={['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map((value) => ({value, label: value}))}/>
        {!follow && <Button onClick={jumpToEnd}>К последним</Button>}
      </Space>
      <div ref={logRef} onScroll={onScroll} style={{
        height: 'calc(100vh - 220px)',
        minHeight: 320,
        overflow: 'auto',
        background: '#111827',
        color: '#e5e7eb',
        padding: 12,
        fontFamily: 'monospace'
      }}>
        {logs.data?.rows.map((row, index) => <div key={`${row.timestamp}-${index}`}><span
          style={{color: '#9ca3af'}}>{row.timestamp}</span> <strong>{row.level}</strong>
          <span>{row.logger}</span> {row.message}</div>)}
      </div>
    </Space>
  </div>;
}
