import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { toast } from '@/components/ui/sonner';
import { Plus, Filter, X, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, MoreVertical } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { CONFIRM_BADGE } from './_shared';

const SHIFT_TYPES = ['Morning', 'Afternoon', 'Evening', 'Night'];
const CONF_STATUSES = ['Not Confirmed', 'Pending', 'Confirmed', 'Declined', 'No Response'];
const CONF_METHODS = ['Call', 'Text', 'Call + Text'];
const SHIFT_STATUSES = ['Not Started', 'Check-in', 'Checkout', 'Late Clock In', 'Early Clock Out', 'Late Clock Out', 'Absent', 'Completed', 'Cancelled'];
const QUICK_ACTIONS = ['Check-in', 'Checkout', 'Late Clock In', 'Late Clock Out', 'Absent'];
const STATUS_BADGE_MAP = {
  'Check-in': 'bg-emerald-100 text-emerald-700',
  'Checkout': 'bg-sky-100 text-sky-700',
  'Late Clock In': 'bg-amber-100 text-amber-700',
  'Late Clock Out': 'bg-amber-100 text-amber-800',
  'Early Clock Out': 'bg-orange-100 text-orange-700',
  'Absent': 'bg-rose-100 text-rose-700',
  'Completed': 'bg-emerald-100 text-emerald-800',
  'Cancelled': 'bg-slate-200 text-slate-600',
  'Not Started': 'bg-slate-100 text-slate-600',
};

const emptyFilters = {
  officer_id: '', vendor_id: '', client_id: '', post_site_id: '', post_pin: '', work_order: '',
  date_from: '', date_to: '', shift_type: '', confirmation_status: '', shift_status: '',
};

const DispatchSchedulePage = ({ todayOnly = false }) => {
  const { user } = useAuthStore();
  const canCreate = hasPermission(user, 'dispatch.schedule.create');
  const canEdit = hasPermission(user, 'dispatch.schedule.edit');
  const canDelete = hasPermission(user, 'dispatch.schedule.delete');
  const canCancel = hasPermission(user, 'dispatch.schedule.cancel');
  const canConfirm = hasPermission(user, 'dispatch.confirmation.manage');
  const canFinancial = hasPermission(user, 'dispatch.financial.view');

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(
    todayOnly ? { ...emptyFilters, date_from: new Date().toISOString().slice(0, 10), date_to: new Date().toISOString().slice(0, 10) } : emptyFilters
  );

  const [clients, setClients] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [officers, setOfficers] = useState([]);
  const [postSites, setPostSites] = useState([]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});

  const [confDialog, setConfDialog] = useState(null);
  const [confForm, setConfForm] = useState({ confirmation_status: 'Confirmed', confirmation_method: 'Call', remarks: '' });
  const [actionsDialog, setActionsDialog] = useState(null);
  const [actions, setActions] = useState([]);
  const [actionsLoading, setActionsLoading] = useState(false);
  const [statusBusy, setStatusBusy] = useState(null);
  const [statusDialog, setStatusDialog] = useState(null); // { row, status }
  const [statusRemarks, setStatusRemarks] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = { page, limit };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const { data } = await api.get('/dispatch/schedules', { params });
      setRows(data.items || []);
      setTotal(data.total || 0);
    } catch (e) { if (!silent) toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { if (!silent) setLoading(false); }
  }, [page, limit, filters]);

  useEffect(() => { load(); }, [load]);
  // Real-time polling — every 10s, silent so no loading flicker
  useEffect(() => {
    const t = setInterval(() => load(true), 10_000);
    return () => clearInterval(t);
  }, [load]);
  useEffect(() => {
    api.get('/dispatch/clients').then(r => setClients(r.data)).catch(() => {});
    api.get('/dispatch/vendors').then(r => setVendors(r.data)).catch(() => {});
    api.get('/dispatch/officers').then(r => setOfficers(r.data)).catch(() => {});
    api.get('/dispatch/post-sites').then(r => setPostSites(r.data)).catch(() => {});
  }, []);

  const openCreate = () => {
    setEditing(null);
    const today = new Date().toISOString().slice(0, 10);
    setForm({ date: today, shift_type: 'Morning', start_time: '08:00', end_time: '16:00' });
    setDialogOpen(true);
  };
  const openEdit = (row) => {
    setEditing(row);
    // Only pick editable fields — do NOT include shift_status, actual_check_in/out or
    // any computed/enriched fields. They should be changed via Quick Actions, not Edit.
    setForm({
      date: row.date, shift_type: row.shift_type,
      start_time: row.start_time, end_time: row.end_time,
      client_id: row.client_id, vendor_id: row.vendor_id,
      post_site_id: row.post_site_id, officer_id: row.officer_id,
      duty_rate: row.duty_rate ?? null,
      billing_rate: row.billing_rate ?? null,
      work_order_number: row.work_order_number ?? null,
      remarks: row.remarks ?? '',
    });
    setDialogOpen(true);
  };

  const submit = async () => {
    // client-side required check
    for (const k of ['date', 'shift_type', 'start_time', 'end_time', 'client_id', 'vendor_id', 'post_site_id', 'officer_id']) {
      if (!form[k]) { toast.error(`${k.replace('_', ' ')} is required`); return; }
    }
    try {
      if (editing) {
        // Send only actually-changed fields so audit stays clean
        const changed = {};
        Object.entries(form).forEach(([k, v]) => {
          const oldV = editing[k];
          const same = (oldV ?? null) === (v ?? null) || (oldV === '' && !v) || (v === '' && !oldV);
          if (!same) changed[k] = v === '' ? null : v;
        });
        if (Object.keys(changed).length === 0) {
          toast.info('No changes to save'); setDialogOpen(false); return;
        }
        await api.put(`/dispatch/schedules/${editing.id}`, changed);
      } else {
        await api.post('/dispatch/schedules', form);
      }
      toast.success(`Schedule ${editing ? 'updated' : 'created'}`);
      setDialogOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const cancelSchedule = async (row) => {
    if (!window.confirm(`Cancel schedule for ${row.officer_name}?`)) return;
    try { await api.post(`/dispatch/schedules/${row.id}/cancel`); toast.success('Cancelled'); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const deleteSchedule = async (row) => {
    if (!window.confirm('Delete permanently?')) return;
    try { await api.delete(`/dispatch/schedules/${row.id}`); toast.success('Deleted'); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const openConfirm = (row, preselectStatus = null) => {
    setConfDialog(row);
    setConfForm({
      confirmation_status: preselectStatus || row.confirmation_status || 'Confirmed',
      confirmation_method: 'Call',
      remarks: ''
    });
  };
  const submitConfirm = async () => {
    try {
      await api.post(`/dispatch/schedules/${confDialog.id}/confirm`, confForm);
      toast.success('Confirmation updated'); setConfDialog(null); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const openActions = async (row) => {
    setActions([]);              // clear stale entries before showing loader
    setActionsLoading(true);
    setActionsDialog(row);
    try { const { data } = await api.get(`/dispatch/schedules/${row.id}/actions`); setActions(data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setActionsLoading(false); }
  };
  const openStatusDialog = (row, status) => {
    if (status === row.shift_status) return;
    setStatusDialog({ row, status });
    setStatusRemarks('');
  };
  const applyStatus = async () => {
    if (!statusDialog) return;
    const { row, status } = statusDialog;
    setStatusBusy(`${row.id}:${status}`);
    try {
      const payload = { shift_status: status, remarks: statusRemarks || null };
      const now = new Date().toTimeString().slice(0, 5);
      if (status === 'Check-in' || status === 'Late Clock In') payload.actual_check_in = now;
      if (status === 'Checkout' || status === 'Late Clock Out' || status === 'Early Clock Out') payload.actual_check_out = now;
      await api.post(`/dispatch/schedules/${row.id}/status`, payload);
      toast.success(`${status} recorded by ${user?.name}`);
      setStatusDialog(null); setStatusRemarks('');
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setStatusBusy(null); }
  };

  const setF = (k, v) => { setFilters({ ...filters, [k]: v }); setPage(1); };
  const activeChips = Object.entries(filters).filter(([k, v]) => v).map(([k, v]) => ({ k, v }));
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6" data-testid="dispatch-schedule-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">
            {todayOnly ? "Today's Dispatch" : 'Dispatch Schedule'}
          </h1>
          <p className="text-sm text-[#64748B] mt-1">{total} record{total !== 1 && 's'}</p>
        </div>
        {canCreate && (
          <Button onClick={openCreate} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="new-schedule-btn">
            <Plus className="w-4 h-4 mr-2" /> New Schedule
          </Button>
        )}
      </div>

      {/* Filters (collapsible) */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl">
        <button
          type="button"
          onClick={() => setFiltersOpen((o) => !o)}
          className="w-full flex items-center justify-between p-4 text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]"
          data-testid="toggle-filters"
        >
          <span className="flex items-center gap-2">
            <Filter className="w-4 h-4" /> Filters
            {activeChips.length > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-[#4F46E5] text-white text-xs font-medium">
                {activeChips.length}
              </span>
            )}
          </span>
          {filtersOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {activeChips.length > 0 && (
          <div className="px-4 pb-3 flex items-center gap-2 flex-wrap border-t border-[#E2E8F0] dark:border-[#27272A] pt-3">
            {activeChips.map(({ k, v }) => (
              <span key={k} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-xs">
                {k.replace('_', ' ')}: {String(v).slice(0, 16)}
                <button onClick={() => setF(k, '')}><X className="w-3 h-3" /></button>
              </span>
            ))}
            <Button variant="ghost" size="sm" onClick={() => { setFilters(emptyFilters); setPage(1); }} data-testid="clear-filters" className="text-xs h-7">
              Clear all
            </Button>
          </div>
        )}

        {filtersOpen && (
          <div className="p-4 pt-0 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><Label className="text-xs">Officer</Label>
                <Select value={filters.officer_id || 'all'} onValueChange={(v) => setF('officer_id', v === 'all' ? '' : v)}>
                  <SelectTrigger data-testid="filter-officer"><SelectValue placeholder="All officers" /></SelectTrigger>
                  <SelectContent><SelectItem value="all">All officers</SelectItem>
                    {officers.map(o => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs">Vendor</Label>
                <Select value={filters.vendor_id || 'all'} onValueChange={(v) => setF('vendor_id', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-vendor"><SelectValue placeholder="All vendors" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All vendors</SelectItem>
                {vendors.map(v => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Client</Label>
            <Select value={filters.client_id || 'all'} onValueChange={(v) => setF('client_id', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-client"><SelectValue placeholder="All clients" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All clients</SelectItem>
                {clients.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Post Site</Label>
            <Select value={filters.post_site_id || 'all'} onValueChange={(v) => setF('post_site_id', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-post-site"><SelectValue placeholder="All post sites" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All post sites</SelectItem>
                {postSites.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Post Pin</Label>
            <Input value={filters.post_pin} onChange={(e) => setF('post_pin', e.target.value)} placeholder="PS-102" data-testid="filter-pin" />
          </div>
          <div><Label className="text-xs">Date From</Label>
            <Input type="date" value={filters.date_from} onChange={(e) => setF('date_from', e.target.value)} data-testid="filter-from" />
          </div>
          <div><Label className="text-xs">Date To</Label>
            <Input type="date" value={filters.date_to} onChange={(e) => setF('date_to', e.target.value)} data-testid="filter-to" />
          </div>
          <div><Label className="text-xs">Shift</Label>
            <Select value={filters.shift_type || 'all'} onValueChange={(v) => setF('shift_type', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-shift"><SelectValue placeholder="All shifts" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All shifts</SelectItem>
                {SHIFT_TYPES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Confirmation</Label>
            <Select value={filters.confirmation_status || 'all'} onValueChange={(v) => setF('confirmation_status', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-conf"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All</SelectItem>
                {CONF_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Shift Status</Label>
            <Select value={filters.shift_status || 'all'} onValueChange={(v) => setF('shift_status', v === 'all' ? '' : v)}>
              <SelectTrigger data-testid="filter-status"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All</SelectItem>
                {SHIFT_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
              <div><Label className="text-xs">Work Order</Label>
                <Input value={filters.work_order} onChange={(e) => setF('work_order', e.target.value)} placeholder="WO-123" data-testid="filter-work-order" />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full min-w-[1400px] text-sm table-auto">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-3 py-3">Date</th><th className="px-3 py-3">Officer</th>
              <th className="px-3 py-3">Post Pin</th><th className="px-3 py-3">Post Site</th>
              <th className="px-3 py-3">Client</th><th className="px-3 py-3">Vendor</th>
              <th className="px-3 py-3">Shift</th><th className="px-3 py-3">Time</th>
              <th className="px-3 py-3">Hours</th>
              {canFinancial && <><th className="px-3 py-3">Duty Rate</th><th className="px-3 py-3">Billing</th></>}
              <th className="px-3 py-3">Confirmation</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Last Modified By</th>
              <th className="px-3 py-3 text-right">Manage</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? <tr><td colSpan={20} className="px-4 py-8 text-center text-[#64748B]">Loading…</td></tr>
            : rows.length === 0 ? <tr><td colSpan={20} className="px-4 py-8 text-center text-[#64748B]">No dispatch schedules found</td></tr>
            : rows.map(r => (
              <tr key={r.id} data-testid={`sched-${r.id}`}>
                <td className="px-3 py-2 text-[#334155] dark:text-[#E4E4E7]">{r.date}</td>
                <td className="px-3 py-2">{r.officer_name || '—'}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.post_pin || '—'}</td>
                <td className="px-3 py-2">{r.post_site_name || '—'}</td>
                <td className="px-3 py-2">{r.client_name || '—'}</td>
                <td className="px-3 py-2">{r.vendor_name || '—'}</td>
                <td className="px-3 py-2">{r.shift_type}</td>
                <td className="px-3 py-2">{r.start_time}–{r.end_time}</td>
                <td className="px-3 py-2">{r.duty_hours}h</td>
                {canFinancial && <><td className="px-3 py-2">{r.duty_rate ?? '—'}</td><td className="px-3 py-2">{r.billing_rate ?? '—'}</td></>}
                <td className="px-3 py-2">
                  {canConfirm && r.shift_status !== 'Cancelled' ? (
                    <Select
                      value={r.confirmation_status}
                      onValueChange={(v) => openConfirm(r, v)}
                    >
                      <SelectTrigger
                        className={`h-8 w-[140px] text-xs font-medium border ${CONFIRM_BADGE[r.confirmation_status] || 'bg-slate-100 text-slate-600'}`}
                        data-testid={`confirmation-select-${r.id}`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CONF_STATUSES.map((s) => (
                          <SelectItem key={s} value={s} data-testid={`confirmation-option-${s.replace(/\s+/g, '-').toLowerCase()}-${r.id}`}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${CONFIRM_BADGE[r.confirmation_status] || 'bg-slate-100 text-slate-600'}`}>{r.confirmation_status}</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {canEdit && r.shift_status !== 'Cancelled' ? (
                    <Select
                      value={r.shift_status}
                      onValueChange={(v) => openStatusDialog(r, v)}
                      disabled={!!statusBusy && statusBusy.startsWith(`${r.id}:`)}
                    >
                      <SelectTrigger
                        className={`h-8 w-[150px] text-xs font-medium border ${STATUS_BADGE_MAP[r.shift_status] || 'bg-slate-100 text-slate-600'}`}
                        data-testid={`status-select-${r.id}`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SHIFT_STATUSES.filter((s) => s !== 'Cancelled').map((s) => (
                          <SelectItem key={s} value={s} data-testid={`status-option-${s.replace(/\s+/g, '-').toLowerCase()}-${r.id}`}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE_MAP[r.shift_status] || 'bg-slate-100 text-slate-600'}`}>{r.shift_status}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs">
                  {r.last_modified_by_name ? (
                    <button
                      type="button"
                      onClick={() => openActions(r)}
                      className="text-left group focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/40 rounded"
                      data-testid={`last-modified-${r.id}`}
                      title="Click to view full history"
                    >
                      <div className="font-medium text-[#4F46E5] group-hover:underline">{r.last_modified_by_name}</div>
                      <div className="text-[10px] text-[#64748B]">
                        {r.last_modified_action || 'Modified'} · {(r.last_modified_at || '').slice(0, 16).replace('T', ' ')}
                      </div>
                    </button>
                  ) : <span className="text-[#64748B]">—</span>}
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  {(canEdit || canCancel || canDelete) ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="ghost" className="h-8 w-8 p-0" data-testid={`row-menu-${r.id}`} aria-label="Row actions">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" data-testid={`row-menu-content-${r.id}`}>
                        {canEdit && (
                          <DropdownMenuItem onClick={() => openEdit(r)} data-testid={`edit-${r.id}`}>
                            Edit
                          </DropdownMenuItem>
                        )}
                        {canCancel && r.shift_status !== 'Cancelled' && (
                          <DropdownMenuItem onClick={() => cancelSchedule(r)} data-testid={`cancel-${r.id}`}>
                            Cancel
                          </DropdownMenuItem>
                        )}
                        {canDelete && (
                          <>
                            {(canEdit || canCancel) && <DropdownMenuSeparator />}
                            <DropdownMenuItem onClick={() => deleteSchedule(r)} data-testid={`delete-${r.id}`}
                              className="text-rose-600 focus:text-rose-600 focus:bg-rose-50 dark:focus:bg-rose-950">
                              Delete
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : <span className="text-[#64748B]">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-[#64748B]">Page {page} of {pages}</div>
        <div className="flex items-center gap-2">
          <Select value={String(limit)} onValueChange={(v) => { setLimit(Number(v)); setPage(1); }}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>{[50, 100, 250].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft className="w-4 h-4" /></Button>
          <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      {/* Create/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit' : 'New'} Dispatch Schedule</DialogTitle>
            <DialogDescription>{editing ? 'Update the shift details for this dispatch.' : 'Assign an officer to a post site for a specific date and shift.'}</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Date *</Label><Input type="date" value={form.date || ''} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="sf-date" /></div>
            <div><Label>Shift *</Label>
              <Select value={form.shift_type || ''} onValueChange={(v) => setForm({ ...form, shift_type: v })}>
                <SelectTrigger data-testid="sf-shift"><SelectValue /></SelectTrigger>
                <SelectContent>{SHIFT_TYPES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Start Time *</Label><Input type="time" value={form.start_time || ''} onChange={(e) => setForm({ ...form, start_time: e.target.value })} data-testid="sf-start" /></div>
            <div><Label>End Time *</Label><Input type="time" value={form.end_time || ''} onChange={(e) => setForm({ ...form, end_time: e.target.value })} data-testid="sf-end" /></div>
            <div><Label>Client *</Label>
              <Select value={form.client_id || ''} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger data-testid="sf-client"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{clients.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Vendor *</Label>
              <Select value={form.vendor_id || ''} onValueChange={(v) => setForm({ ...form, vendor_id: v })}>
                <SelectTrigger data-testid="sf-vendor"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{vendors.map(v => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Post Site *</Label>
              <Select value={form.post_site_id || ''} onValueChange={(v) => {
                const p = postSites.find(x => x.id === v);
                setForm({ ...form, post_site_id: v, client_id: p?.client_id || form.client_id, vendor_id: p?.vendor_id || form.vendor_id });
              }}>
                <SelectTrigger data-testid="sf-post"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{postSites.map(p => <SelectItem key={p.id} value={p.id}>{p.post_pin} — {p.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Security Officer *</Label>
              <Select value={form.officer_id || ''} onValueChange={(v) => setForm({ ...form, officer_id: v })}>
                <SelectTrigger data-testid="sf-officer"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{officers.filter(o => o.status === 'active').map(o => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {canFinancial && <>
              <div><Label>Duty Rate</Label><Input type="number" value={form.duty_rate ?? ''} onChange={(e) => setForm({ ...form, duty_rate: e.target.value ? Number(e.target.value) : null })} data-testid="sf-duty-rate" /></div>
              <div><Label>Billing Rate</Label><Input type="number" value={form.billing_rate ?? ''} onChange={(e) => setForm({ ...form, billing_rate: e.target.value ? Number(e.target.value) : null })} data-testid="sf-billing-rate" /></div>
              <div className="col-span-2"><Label>Work Order Number</Label><Input value={form.work_order_number ?? ''} onChange={(e) => setForm({ ...form, work_order_number: e.target.value })} data-testid="sf-wo" /></div>
            </>}
            <div className="col-span-2"><Label>Remarks</Label><Textarea value={form.remarks ?? ''} onChange={(e) => setForm({ ...form, remarks: e.target.value })} data-testid="sf-remarks" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={submit} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-schedule">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation dialog */}
      <Dialog open={!!confDialog} onOpenChange={(o) => !o && setConfDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Confirmation</DialogTitle>
            <DialogDescription>Record the confirmation contact status, method and any notes.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div><Label>Status</Label>
              <Select value={confForm.confirmation_status} onValueChange={(v) => setConfForm({ ...confForm, confirmation_status: v })}>
                <SelectTrigger data-testid="cf-status"><SelectValue /></SelectTrigger>
                <SelectContent>{CONF_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Method</Label>
              <Select value={confForm.confirmation_method} onValueChange={(v) => setConfForm({ ...confForm, confirmation_method: v })}>
                <SelectTrigger data-testid="cf-method"><SelectValue /></SelectTrigger>
                <SelectContent>{CONF_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Remarks</Label><Textarea value={confForm.remarks} onChange={(e) => setConfForm({ ...confForm, remarks: e.target.value })} data-testid="cf-remarks" /></div>
            <p className="text-xs text-[#64748B]">Confirmed by: <b>{user?.name}</b> ({user?.role})</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfDialog(null)}>Cancel</Button>
            <Button onClick={submitConfirm} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-confirmation">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Status change remark dialog */}
      <Dialog open={!!statusDialog} onOpenChange={(o) => !o && setStatusDialog(null)}>
        <DialogContent data-testid="status-remark-dialog">
          <DialogHeader>
            <DialogTitle>Update Status</DialogTitle>
            <DialogDescription>
              Changing status to <b>{statusDialog?.status}</b>. Add an optional remark for the history.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Remark (optional)</Label>
              <Textarea
                value={statusRemarks}
                onChange={(e) => setStatusRemarks(e.target.value)}
                placeholder="e.g. Officer arrived 5 minutes late due to traffic"
                data-testid="status-remark-input"
              />
            </div>
            <p className="text-xs text-[#64748B]">
              Recorded by: <b>{user?.name}</b> ({user?.role})
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusDialog(null)}>Cancel</Button>
            <Button
              onClick={applyStatus}
              className="bg-[#4F46E5] hover:bg-[#4338CA]"
              disabled={!!statusBusy}
              data-testid="save-status-remark"
            >
              {statusBusy ? 'Saving…' : `Confirm ${statusDialog?.status || ''}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Full History dialog — unified: check-ins, checkouts, edits, cancels, confirmations */}
      <Dialog open={!!actionsDialog} onOpenChange={(o) => !o && setActionsDialog(null)}>
        <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto" data-testid="actions-dialog">
          <DialogHeader>
            <DialogTitle>Full History</DialogTitle>
            <DialogDescription>Check-ins, checkouts, confirmations, edits and everything else — newest first.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {actionsLoading ? <p className="text-sm text-[#64748B]">Loading history…</p>
              : actions.length === 0 ? <p className="text-sm text-[#64748B]">No actions recorded yet.</p>
              : actions.map(a => (
                <div key={a.id} className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{a.actor_name || 'Unknown'}</span>
                      {a.actor_role && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">
                          {a.actor_role.replace(/_/g, ' ')}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[#64748B]">{a.at?.slice(0, 16).replace('T', ' ')}</span>
                  </div>
                  <div className="mt-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE_MAP[a.action] || 'bg-indigo-100 text-indigo-700'}`}>
                      {a.action}
                    </span>
                  </div>
                  {(a.old_value != null || a.new_value != null) && typeof a.old_value !== 'object' && typeof a.new_value !== 'object' && (
                    <div className="text-xs text-[#64748B] mt-2">
                      <span className="line-through">{a.old_value ?? '—'}</span>
                      {' → '}
                      <span className="font-medium text-[#334155] dark:text-[#E4E4E7]">{a.new_value ?? '—'}</span>
                    </div>
                  )}
                  {(typeof a.old_value === 'object' && a.old_value !== null) && (
                    <div className="text-xs text-[#64748B] mt-2 space-y-0.5">
                      {Object.keys(a.new_value || {}).map((k) => (
                        <div key={k}>
                          <span className="text-[10px] uppercase tracking-wider">{k.replace(/_/g, ' ')}: </span>
                          <span className="line-through">{String(a.old_value?.[k] ?? '—')}</span>
                          {' → '}
                          <span className="font-medium text-[#334155] dark:text-[#E4E4E7]">{String(a.new_value?.[k] ?? '—')}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {a.remarks && <div className="text-sm mt-2 text-[#334155] dark:text-[#E4E4E7] italic">"{a.remarks}"</div>}
                </div>
              ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DispatchSchedulePage;
