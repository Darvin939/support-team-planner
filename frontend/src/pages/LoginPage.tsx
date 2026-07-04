import {useState} from 'react';
import {Alert, Button, Card, Form, Input, Select, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';

interface EmployeeOption {
  id: number;
  last_name: string;
  first_name: string;
  middle_name: string | null;
}

function useLoginEmployees() {
  return useQuery<EmployeeOption[]>({
    queryKey: ['login-employees'],
    queryFn: async () => {
      const r = await fetch('/api/login-employees', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/login-employees -> ${r.status}`);
      return r.json();
    },
  });
}

export function LoginPage({ isDark, onToggleTheme }: { isDark: boolean; onToggleTheme: () => void }) {
  const { data: employees, isLoading } = useLoginEmployees();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: { employee_id: number; password: string }) {
    setError(null);
    setSubmitting(true);
    try {
      const body = new URLSearchParams();
      body.set('employee_id', String(values.employee_id));
      body.set('password', values.password);
      const r = await fetch('/login', { method: 'POST', body, credentials: 'same-origin' });
      const data = await r.json();
      if (!r.ok) {
        setError(data.error ?? 'Не удалось войти');
        setSubmitting(false);
        return;
      }
      window.location.href = '/planning';
    } catch {
      setError('Не удалось связаться с сервером');
      setSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <button
        onClick={onToggleTheme}
        style={{
          position: 'fixed', top: 16, right: 16, width: 36, height: 36,
          border: '1px solid rgba(128,128,128,0.3)', borderRadius: 6, background: 'none', cursor: 'pointer',
        }}
        aria-label="Переключить тему"
        type="button"
      >
        {isDark ? '☾' : '☀'}
      </button>

      <Card style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4, fontWeight: 700, fontSize: '1.05rem' }}>
          <svg width="24" height="24" viewBox="0 0 20 20" fill="none" stroke="#1668dc" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="14" height="14" rx="3" />
            <path d="M3 8.5h14M8.2 3v14" />
          </svg>
          <span>
            Пульт<span style={{ color: '#1668dc' }}>.</span>Планировщик
          </span>
        </div>
        <Typography.Title level={4} style={{ marginTop: 8 }}>
          Вход в систему
        </Typography.Title>

        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

        <Form layout="vertical" onFinish={handleSubmit} disabled={submitting}>
          <Form.Item name="employee_id" label="Сотрудник" rules={[{ required: true, message: 'Выберите сотрудника' }]}>
            <Select
              placeholder="— выберите —"
              loading={isLoading}
              showSearch
              optionFilterProp="label"
              options={employees?.map((e) => ({
                value: e.id,
                label: `${e.last_name} ${e.first_name}${e.middle_name ? ' ' + e.middle_name : ''}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              Войти
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
