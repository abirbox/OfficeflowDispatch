import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { toast } from '@/components/ui/sonner';
import { Download, FileText, FileSpreadsheet } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';

const isoToday = () => new Date().toISOString().slice(0, 10);
const isoDaysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };

const REPORT_TABS = [
  { key: 'schedules', label: 'Schedules', endpoint: '/dispatch/reports/schedules',
    columns: [
      { key: 'date', label: 'Date' }, { key: 'officer_name', label: 'Officer' },
      { key: 'post_pin', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
      { key: 'client_name', label: 'Client' }, { key: 'vendor_name', label: 'Vendor' },
      { key: 'shift_type', label: 'Shift' }, { key: 'start_time', label: 'Start' }, { key: 'end_time', label: 'End' },
      { key: 'duty_hours', label: 'Hours' }, { key: 'confirmation_status', label: 'Confirmation' },
      { key: 'shift_status', label: 'Status' },
    ],
    financialColumns: [{ key: 'duty_rate', label: 'Duty Rate' }, { key: 'billing_rate', label: 'Billing' }, { key: 'work_order_number', label: 'W.O.' }] },
  { key: 'by-officer', label: 'By Officer', endpoint: '/dispatch/reports/by-officer',
    columns: [
      { key: 'officer_name', label: 'Officer' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' }, { key: 'absent', label: 'Absent' },
      { key: 'late', label: 'Late' }, { key: 'early_checkout', label: 'Early Out' },
      { key: 'total_hours', label: 'Total Hours' }, { key: 'attendance_pct', label: 'Attendance %' },
    ],
    financialColumns: [{ key: 'billing_amount', label: 'Billing' }, { key: 'cost_amount', label: 'Cost' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-post-site', label: 'By Post Site', endpoint: '/dispatch/reports/by-post-site',
    columns: [
      { key: 'post_pin', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
      { key: 'required_officers', label: 'Required' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' }, { key: 'absent', label: 'Absent' },
      { key: 'late', label: 'Late' }, { key: 'total_hours', label: 'Hours' },
      { key: 'coverage_pct', label: 'Coverage %' },
    ],
    financialColumns: [{ key: 'billing_amount', label: 'Billing' }, { key: 'cost_amount', label: 'Cost' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-client', label: 'By Client', endpoint: '/dispatch/reports/by-client',
    columns: [
      { key: 'client_name', label: 'Client' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' }, { key: 'absent', label: 'Absent' },
      { key: 'late', label: 'Late' }, { key: 'total_hours', label: 'Hours' },
    ],
    financialColumns: [{ key: 'billing_amount', label: 'Billing' }, { key: 'cost_amount', label: 'Cost' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-vendor', label: 'By Vendor', endpoint: '/dispatch/reports/by-vendor',
    columns: [
      { key: 'vendor_name', label: 'Vendor' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' }, { key: 'absent', label: 'Absent' },
      { key: 'late', label: 'Late' }, { key: 'total_hours', label: 'Hours' },
    ],
    financialColumns: [{ key: 'billing_amount', label: 'Billing' }, { key: 'cost_amount', label: 'Cost' }, { key: 'margin', label: 'Margin' }] },
];

const DispatchReportsPage = () => {
  const { user } = useAuthStore();
  const canView = hasPermission(user, 'dispatch.reports.view');
  const canExport = hasPermission(user, 'dispatch.reports.export');
  const canFinancial = hasPermission(user, 'dispatch.financial.view');

  const [active, setActive] = useState('schedules');
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(30));
  const [dateTo, setDateTo] = useState(isoToday());
  const [limit, setLimit] = useState(50);
  const [data, setData] = useState({ items: [], count: 0 });
  const [loading, setLoading] = useState(false);

  const cfg = REPORT_TABS.find((t) => t.key === active);

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    try {
      const params = { date_from: dateFrom, date_to: dateTo };
      if (active === 'schedules') params.limit = limit;
      const { data } = await api.get(cfg.endpoint, { params });
      setData(data);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [active, dateFrom, dateTo, limit, cfg.endpoint, canView]);

  useEffect(() => { load(); }, [load]);

  const download = async (format) => {
    try {
      const params = { type: active, format, date_from: dateFrom, date_to: dateTo };
      const res = await api.get('/dispatch/reports/export', { params, responseType: 'blob' });
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `dispatch-${active}-${dateFrom}-${dateTo}.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} downloaded`);
    } catch (e) {
      // blob errors need decoding
      try {
        const text = await e.response?.data?.text?.();
        const detail = text ? JSON.parse(text).detail : null;
        toast.error(detail || 'Export failed');
      } catch { toast.error('Export failed'); }
    }
  };

  if (!canView) return <div className="p-8 text-[#64748B]" data-testid="reports-no-access">You do not have permission to view Dispatch reports.</div>;

  const cols = [...cfg.columns, ...(canFinancial ? cfg.financialColumns : [])];

  return (
    <div className="space-y-6" data-testid="dispatch-reports-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Dispatch Reports</h1>
          <p className="text-sm text-[#64748B] mt-1">
            {data.count} record{data.count !== 1 && 's'} · Financial data {canFinancial ? 'visible' : 'hidden'}
          </p>
        </div>
        {canExport && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => download('csv')} data-testid="export-csv">
              <FileSpreadsheet className="w-4 h-4 mr-2" /> Export CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => download('pdf')} data-testid="export-pdf">
              <FileText className="w-4 h-4 mr-2" /> Export PDF
            </Button>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <div><Label className="text-xs">Date From</Label><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} data-testid="rf-from" /></div>
        <div><Label className="text-xs">Date To</Label><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} data-testid="rf-to" /></div>
        {active === 'schedules' && (
          <div><Label className="text-xs">Limit</Label>
            <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
              <SelectTrigger data-testid="rf-limit"><SelectValue /></SelectTrigger>
              <SelectContent>{[50, 100, 250, 500, 1000].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        )}
        <div className="flex items-end">
          <p className="text-xs text-[#64748B]">Max 3 months (92 days). Latest {active === 'schedules' ? limit : 'aggregated'} shown by default.</p>
        </div>
      </div>

      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="grid grid-cols-5 max-w-2xl">
          {REPORT_TABS.map((t) => <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`}>{t.label}</TabsTrigger>)}
        </TabsList>
        {REPORT_TABS.map((t) => (
          <TabsContent key={t.key} value={t.key} className="mt-4">
            <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
                  <tr>{cols.map((c) => <th key={c.key} className="px-3 py-3">{c.label}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                  {loading ? <tr><td colSpan={cols.length} className="px-4 py-8 text-center text-[#64748B]">Loading…</td></tr>
                  : (data.items || []).length === 0 ? <tr><td colSpan={cols.length} className="px-4 py-8 text-center text-[#64748B]">No data</td></tr>
                  : data.items.map((r, i) => (
                    <tr key={r.id || `${r.officer_id || r.client_id || r.vendor_id || r.post_site_id || i}`} data-testid={`report-row-${i}`}>
                      {cols.map((c) => <td key={c.key} className="px-3 py-2 text-[#334155] dark:text-[#E4E4E7]">{r[c.key] ?? '—'}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default DispatchReportsPage;
