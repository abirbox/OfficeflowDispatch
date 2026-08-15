import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/axios';

const AppSettingsContext = createContext({
  settings: null,
  loading: true,
  refresh: () => {},
});

const DEFAULTS = {
  brand_name: 'OfficeFlow',
  brand_logo_url: null,
  login_hero_title: 'OfficeFlow',
  login_hero_subtitle: 'Modern Office Management, HR, Attendance, GPS Tracking & Task Management Platform',
  login_welcome_title: 'Welcome Back',
  login_welcome_subtitle: 'Sign in to your OfficeFlow account',
  currency: 'BDT',
  currency_symbol: '৳',
  timezone: 'Asia/Dhaka',
  tz_offset_hours: 6.0,
};

export const AppSettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      // Prefer authenticated endpoint if user is logged in; fall back to public
      let data;
      try {
        const r = await api.get('/settings');
        data = r.data;
      } catch {
        const r = await api.get('/settings/public');
        data = r.data;
      }
      setSettings({ ...DEFAULTS, ...data });
    } catch {
      setSettings(DEFAULTS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <AppSettingsContext.Provider value={{ settings, loading, refresh, setSettings }}>
      {children}
    </AppSettingsContext.Provider>
  );
};

export const useAppSettings = () => useContext(AppSettingsContext);

export const formatMoney = (amount, symbol = '৳') => {
  const n = Number(amount || 0);
  return `${symbol} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
