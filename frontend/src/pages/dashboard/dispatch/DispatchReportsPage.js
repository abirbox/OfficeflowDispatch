import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from '@/components/ui/sonner';
import { Download, FileText, FileSpreadsheet, ChevronRight } from 'lucide-react';
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

  // Map report tab key → entity_type for the drill-down detail dialog
  const ENTITY_TYPE_BY_TAB = { 'by-officer': 'officer', 'by-post-site': 'post_site', 'by-client': 'client', 'by-vendor': 'vendor' };
  const ENTITY_ID_KEY = { 'by-officer': 'officer_id', 'by-post-site': 'post_site_id', 'by-client': 'client_id', 'by-vendor': 'vendor_id' };
  const ENTITY_NAME_KEY = { 'by-officer': 'officer_name', 'by-post-site': 'post_site_name', 'by-client': 'client_name', 'by-vendor': 'vendor_name' };

  const [detail, setDetail] = useState(null); // { entity_type, entity_id, data }
  const [detailLoading, setDetailLoading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickedCols, setPickedCols] = useState([]);

  const openDetail = async (row) => {
    const entity_type = ENTITY_TYPE_BY_TAB[active];
    const entity_id = row[ENTITY_ID_KEY[active]];
    if (!entity_type || !entity_id) return;
    setDetail({ entity_type, entity_id, entity_name: row[ENTITY_NAME_KEY[active]] });
    setDetailLoading(true);
    // Initialize picker with ALL allowed columns
    const allKeys = [...ENTITY_EXPORT_COLS.map(c => c.key), ...(canFinancial ? ENTITY_EXPORT_COLS_FIN.map(c => c.key) : [])];
    setPickedCols(allKeys);
    try {
      const { data } = await api.get('/dispatch/reports/entity-detail', {
        params: { entity_type, entity_id, date_from: dateFrom, date_to: dateTo }
      });
      setDetail((d) => ({ ...d, data }));
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setDetailLoading(false); }
  };

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
                  : data.items.map((r, i) => {
                    const clickable = ENTITY_TYPE_BY_TAB[t.key];
                    return (
                    <tr
                      key={r.id || `${r.officer_id || r.client_id || r.vendor_id || r.post_site_id || i}`}
                      data-testid={`report-row-${i}`}
                      className={clickable ? 'hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F11] cursor-pointer' : ''}
                      onClick={clickable ? () => openDetail(r) : undefined}
                    >
                      {cols.map((c, j) => (
                        <td key={c.key} className="px-3 py-2 text-[#334155] dark:text-[#E4E4E7]">
                          {j === 0 && clickable ? (
                            <span className="text-[#4F46E5] hover:underline font-medium inline-flex items-center gap-1">
                              {r[c.key] ?? '—'} <ChevronRight className="w-3 h-3" />
                            </span>
                          ) : (r[c.key] ?? '—')}
                        </td>
                      ))}
                    </tr>
                  );})}
                </tbody>
              </table>
            </div>
          </TabsContent>
        ))}
      </Tabs>

      {/* Entity Detail Dialog — day-by-day breakdown */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) { setDetail(null); setPickerOpen(false); } }}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="entity-detail-dialog">
          <DialogHeader>
            <DialogTitle>{detail?.entity_type?.replace('_', ' ')} Detail — {detail?.entity_name}</DialogTitle>
            <DialogDescription>
              Full day-by-day breakdown between {dateFrom} and {dateTo}
            </DialogDescription>
          </DialogHeader>
          {detailLoading ? <p className="text-sm text-[#64748B]">Loading detail…</p>
            : detail?.data && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(detail.data.summary || {}).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-[#E2E8F0] dark:border-[#27272A] p-3">
                      <p className="text-[10px] uppercase tracking-wider text-[#64748B]">{k.replace(/_/g, ' ')}</p>
                      <p className="text-lg font-bold text-[#0F172A] dark:text-[#FAFAFA]">{v}</p>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Shifts ({detail.data.count})</h3>
                  {canExport && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => setPickerOpen(true)} data-testid="detail-pick-columns">
                        <Download className="w-4 h-4 mr-2" /> Choose columns & export
                      </Button>
                    </div>
                  )}
                </div>

                <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg overflow-x-auto">
                  <table className="w-full text-xs min-w-[1200px]">
                    <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] uppercase tracking-wider text-[#64748B]">
                      <tr>
                        <th className="px-2 py-2 text-left">Date</th>
                        <th className="px-2 py-2 text-left">Shift</th>
                        <th className="px-2 py-2 text-left">Scheduled</th>
                        <th className="px-2 py-2 text-left">Check-in</th>
                        <th className="px-2 py-2 text-left">Check-out</th>
                        <th className="px-2 py-2 text-left">Hours</th>
                        <th className="px-2 py-2 text-left">Post</th>
                        <th className="px-2 py-2 text-left">Officer</th>
                        <th className="px-2 py-2 text-left">Client / Vendor</th>
                        <th className="px-2 py-2 text-left">Confirmation</th>
                        <th className="px-2 py-2 text-left">Status</th>
                        <th className="px-2 py-2 text-left">Remarks</th>
                        {canFinancial && <>
                          <th className="px-2 py-2 text-left">Duty Rate</th>
                          <th className="px-2 py-2 text-left">Billing</th>
                          <th className="px-2 py-2 text-left">W.O.</th>
                        </>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                      {detail.data.items.map((r) => (
                        <tr key={r.id}>
                          <td className="px-2 py-2">{r.date}</td>
                          <td className="px-2 py-2">{r.shift_type}</td>
                          <td className="px-2 py-2 font-mono">{r.start_time}–{r.end_time}</td>
                          <td className="px-2 py-2 font-mono">{r.actual_check_in || '—'}</td>
                          <td className="px-2 py-2 font-mono">{r.actual_check_out || '—'}</td>
                          <td className="px-2 py-2">{r.duty_hours}h</td>
                          <td className="px-2 py-2">{r.post_pin} — {r.post_site_name}</td>
                          <td className="px-2 py-2">{r.officer_name}</td>
                          <td className="px-2 py-2">{r.client_name} / {r.vendor_name}</td>
                          <td className="px-2 py-2">{r.confirmation_status}{r.confirmation_method ? ` (${r.confirmation_method})` : ''}</td>
                          <td className="px-2 py-2">{r.shift_status}</td>
                          <td className="px-2 py-2 max-w-[220px] truncate" title={r.remarks || ''}>{r.remarks || '—'}</td>
                          {canFinancial && <>
                            <td className="px-2 py-2">{r.duty_rate ?? '—'}</td>
                            <td className="px-2 py-2">{r.billing_rate ?? '—'}</td>
                            <td className="px-2 py-2">{r.work_order_number ?? '—'}</td>
                          </>}
                        </tr>
                      ))}
                      {detail.data.items.length === 0 && (
                        <tr><td colSpan={20} className="px-4 py-6 text-center text-[#64748B]">No shifts in this range</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
        </DialogContent>
      </Dialog>

      {/* Column Picker dialog — used for entity-detail export */}
      <ColumnPickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        canFinancial={canFinancial}
        picked={pickedCols}
        onChange={setPickedCols}
        onExport={async (fmt) => {
          try {
            const params = {
              entity_type: detail.entity_type,
              entity_id: detail.entity_id,
              date_from: dateFrom,
              date_to: dateTo,
              format: fmt,
              columns: pickedCols.join(',') || undefined,
            };
            const res = await api.get('/dispatch/reports/export/entity-detail', { params, responseType: 'blob' });
            const blob = new Blob([res.data], { type: fmt === 'csv' ? 'text/csv' : 'application/pdf' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dispatch-${detail.entity_type}-${detail.entity_id}-${dateFrom}-${dateTo}.${fmt}`;
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
            toast.success(`${fmt.toUpperCase()} downloaded`);
            setPickerOpen(false);
          } catch (e) { toast.error('Export failed'); }
        }}
      />
    </div>
  );
};

const ENTITY_EXPORT_COLS = [
  { key: 'date', label: 'Date' }, { key: 'shift_type', label: 'Shift' },
  { key: 'start_time', label: 'Scheduled Start' }, { key: 'end_time', label: 'Scheduled End' },
  { key: 'actual_check_in', label: 'Actual Check-In' }, { key: 'actual_check_out', label: 'Actual Check-Out' },
  { key: 'duty_hours', label: 'Hours' },
  { key: 'officer_name', label: 'Officer' },
  { key: 'post_pin', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
  { key: 'client_name', label: 'Client' }, { key: 'vendor_name', label: 'Vendor' },
  { key: 'confirmation_status', label: 'Confirmation' }, { key: 'confirmation_method', label: 'Method' },
  { key: 'shift_status', label: 'Shift Status' }, { key: 'remarks', label: 'Remarks' },
  { key: 'last_modified_by_name', label: 'Last Modified By' },
  { key: 'last_modified_action', label: 'Last Action' },
];
const ENTITY_EXPORT_COLS_FIN = [
  { key: 'duty_rate', label: 'Duty Rate' },
  { key: 'billing_rate', label: 'Billing Rate' },
  { key: 'work_order_number', label: 'Work Order' },
];

const ColumnPickerDialog = ({ open, onClose, canFinancial, picked, onChange, onExport }) => {
  const all = canFinancial ? [...ENTITY_EXPORT_COLS, ...ENTITY_EXPORT_COLS_FIN] : ENTITY_EXPORT_COLS;
  const set = new Set(picked);
  const toggle = (k) => { const n = new Set(set); n.has(k) ? n.delete(k) : n.add(k); onChange(Array.from(n)); };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="column-picker-dialog">
        <DialogHeader>
          <DialogTitle>Choose columns to export</DialogTitle>
          <DialogDescription>
            Tick the columns you want in the file. Order is preserved from top → bottom of this list.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-2">
          {all.map((c) => (
            <label key={c.key} className="flex items-center gap-2 text-sm cursor-pointer" data-testid={`col-${c.key}`}>
              <Checkbox checked={set.has(c.key)} onCheckedChange={() => toggle(c.key)} />
              <span className="text-[#334155] dark:text-[#E4E4E7]">{c.label}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-between pt-2">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onChange(all.map((c) => c.key))} data-testid="col-select-all">Select all</Button>
            <Button variant="outline" size="sm" onClick={() => onChange([])} data-testid="col-clear-all">Clear</Button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onExport('csv')} data-testid="detail-export-csv" disabled={picked.length === 0}>
              <FileSpreadsheet className="w-4 h-4 mr-2" /> CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => onExport('pdf')} data-testid="detail-export-pdf" disabled={picked.length === 0}>
              <FileText className="w-4 h-4 mr-2" /> PDF
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default DispatchReportsPage;
