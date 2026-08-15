import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/sonner';
import { Building2, Image as ImageIcon, Globe, DollarSign, Save } from 'lucide-react';
import { useAppSettings } from '@/contexts/AppSettingsContext';

const BrandingTab = () => {
  const { settings, refresh } = useAppSettings();
  const [form, setForm] = useState(null);
  const [currencies, setCurrencies] = useState([]);
  const [timezones, setTimezones] = useState([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { if (settings) setForm({ ...settings }); }, [settings]);

  useEffect(() => {
    (async () => {
      try {
        const [c, t] = await Promise.all([
          api.get('/settings/currencies'),
          api.get('/settings/timezones'),
        ]);
        setCurrencies(c.data);
        setTimezones(t.data);
      } catch { /* silent */ }
    })();
  }, []);

  if (!form) return <div className="p-6 text-sm text-[#64748B]">Loading…</div>;

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        brand_name: form.brand_name,
        login_hero_title: form.login_hero_title,
        login_hero_subtitle: form.login_hero_subtitle,
        login_welcome_title: form.login_welcome_title,
        login_welcome_subtitle: form.login_welcome_subtitle,
        currency: form.currency,
        currency_symbol: form.currency_symbol,
        timezone: form.timezone,
      };
      await api.put('/settings', payload);
      await refresh();
      toast.success('Settings saved. Changes visible everywhere.');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post('/settings/logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      await refresh();
      toast.success('Logo uploaded');
    } catch (err) {
      toast.error('Failed to upload logo');
    } finally {
      setUploading(false);
    }
  };

  const onCurrencyChange = (code) => {
    const c = currencies.find((x) => x.code === code);
    setForm({ ...form, currency: code, currency_symbol: c?.symbol || form.currency_symbol });
  };

  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="branding-tab-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="w-5 h-5" /> Branding & Localization
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Brand identity */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Brand Identity</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Website / App Name</Label>
              <Input
                value={form.brand_name || ''}
                onChange={(e) => setForm({ ...form, brand_name: e.target.value })}
                placeholder="OfficeFlow"
                data-testid="settings-brand-name"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><ImageIcon className="w-4 h-4" /> Logo</Label>
              <div className="flex items-center gap-3">
                {form.brand_logo_url && (
                  <img src={form.brand_logo_url} alt="logo" className="w-10 h-10 rounded object-contain border border-[#E2E8F0]" />
                )}
                <label className="cursor-pointer">
                  <input type="file" accept="image/*" onChange={uploadLogo} className="hidden" data-testid="settings-logo-input" />
                  <span className={`inline-flex items-center px-3 py-2 rounded-lg text-sm border ${uploading ? 'opacity-60' : 'hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]'} border-[#E2E8F0] dark:border-[#27272A]`}>
                    {uploading ? 'Uploading…' : (form.brand_logo_url ? 'Replace Logo' : 'Upload Logo')}
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Login page content */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Login Page Content</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Welcome Title</Label>
              <Input
                value={form.login_welcome_title || ''}
                onChange={(e) => setForm({ ...form, login_welcome_title: e.target.value })}
                placeholder="Welcome Back"
                data-testid="settings-welcome-title"
              />
            </div>
            <div className="space-y-2">
              <Label>Welcome Subtitle</Label>
              <Input
                value={form.login_welcome_subtitle || ''}
                onChange={(e) => setForm({ ...form, login_welcome_subtitle: e.target.value })}
                placeholder="Sign in to your account"
                data-testid="settings-welcome-subtitle"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Hero Title (large right-side text)</Label>
            <Input
              value={form.login_hero_title || ''}
              onChange={(e) => setForm({ ...form, login_hero_title: e.target.value })}
              placeholder="OfficeFlow"
              data-testid="settings-hero-title"
            />
          </div>
          <div className="space-y-2">
            <Label>Hero Subtitle / Tagline</Label>
            <Textarea
              value={form.login_hero_subtitle || ''}
              onChange={(e) => setForm({ ...form, login_hero_subtitle: e.target.value })}
              placeholder="Modern Office Management, HR, Attendance, GPS Tracking & Task Management Platform"
              rows={3}
              data-testid="settings-hero-subtitle"
            />
          </div>
        </div>

        {/* Localization */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Localization</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><DollarSign className="w-4 h-4" /> Currency</Label>
              <Select value={form.currency} onValueChange={onCurrencyChange}>
                <SelectTrigger data-testid="settings-currency"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {currencies.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.symbol} · {c.code} — {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Currency Symbol</Label>
              <Input
                value={form.currency_symbol || ''}
                onChange={(e) => setForm({ ...form, currency_symbol: e.target.value })}
                placeholder="৳"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><Globe className="w-4 h-4" /> Timezone</Label>
              <Select value={form.timezone} onValueChange={(v) => setForm({ ...form, timezone: v })}>
                <SelectTrigger data-testid="settings-timezone"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {timezones.map((t) => (
                    <SelectItem key={t.code} value={t.code}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={save} disabled={saving} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-branding-button">
            <Save className="w-4 h-4 mr-2" /> {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default BrandingTab;
