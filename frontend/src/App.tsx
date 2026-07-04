import {useEffect, useState} from 'react';
import {ConfigProvider} from 'antd';
import ruRU from 'antd/locale/ru_RU';
import {QueryClientProvider} from '@tanstack/react-query';
import {BrowserRouter, Navigate, Route, Routes} from 'react-router-dom';
import {queryClient} from './queryClient';
import {LoginPage} from './pages/LoginPage';
import {StatisticsPage} from './pages/StatisticsPage';
import {JournalPage} from './pages/JournalPage';
import {AuthenticatedLayout} from './components/AuthenticatedLayout';
import {darkTheme, lightTheme} from './theme';

function Shell() {
  const [isDark, setIsDark] = useState(() => (localStorage.getItem('theme') ?? '') !== 'light');

  useEffect(() => {
    localStorage.setItem('theme', isDark ? '' : 'light');
  }, [isDark]);

  const toggleTheme = () => setIsDark((v) => !v);

  return (
    <ConfigProvider theme={isDark ? darkTheme : lightTheme} locale={ruRU}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage isDark={isDark} onToggleTheme={toggleTheme} />} />
          <Route element={<AuthenticatedLayout isDark={isDark} onToggleTheme={toggleTheme} />}>
            <Route path="/statistics" element={<StatisticsPage />} />
            <Route path="/journal" element={<JournalPage />} />
            <Route path="/journal/:teamId" element={<JournalPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell />
    </QueryClientProvider>
  );
}
