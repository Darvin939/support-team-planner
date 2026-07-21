import {lazy, Suspense, useEffect, useState} from 'react';
import {ConfigProvider, Spin} from 'antd';
import ruRU from 'antd/locale/ru_RU';
import {QueryClientProvider} from '@tanstack/react-query';
import {BrowserRouter, Navigate, Route, Routes} from 'react-router-dom';
import {queryClient} from './queryClient';
import {AuthenticatedLayout} from './components/AuthenticatedLayout';
import {darkTheme, lightTheme} from './theme';

const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({default: m.LoginPage})));
const StatisticsPage = lazy(() => import('./pages/StatisticsPage').then((m) => ({default: m.StatisticsPage})));
const JournalPage = lazy(() => import('./pages/JournalPage').then((m) => ({default: m.JournalPage})));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({default: m.SettingsPage})));
const PlanningPage = lazy(() => import('./pages/PlanningPage').then((m) => ({default: m.PlanningPage})));

function PageFallback() {
  return (
    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh'}}>
      <Spin size="large"/>
    </div>
  );
}

function Shell() {
  const [isDark, setIsDark] = useState(() => (localStorage.getItem('theme') ?? '') !== 'light');

  useEffect(() => {
    localStorage.setItem('theme', isDark ? '' : 'light');
  }, [isDark]);

  const toggleTheme = () => setIsDark((v) => !v);

  return (
    <ConfigProvider theme={isDark ? darkTheme : lightTheme} locale={ruRU}>
      <BrowserRouter>
        <Suspense fallback={<PageFallback/>}>
          <Routes>
            <Route path="/login" element={<LoginPage isDark={isDark} onToggleTheme={toggleTheme}/>}/>
            <Route element={<AuthenticatedLayout isDark={isDark} onToggleTheme={toggleTheme}/>}>
              <Route path="/statistics" element={<StatisticsPage/>}/>
              <Route path="/journal" element={<JournalPage/>}/>
              <Route path="/journal/:teamId" element={<JournalPage/>}/>
              <Route path="/settings" element={<SettingsPage/>}/>
              <Route path="/planning" element={<PlanningPage/>}/>
              <Route path="/planning/:teamId" element={<PlanningPage/>}/>
            </Route>
            <Route path="*" element={<Navigate to="/login" replace/>}/>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell/>
    </QueryClientProvider>
  );
}
