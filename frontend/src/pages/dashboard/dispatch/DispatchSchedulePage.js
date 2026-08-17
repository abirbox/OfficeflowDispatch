import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { Plus, Filter, X, ChevronLeft, ChevronRight, Phone, MessageSquare, History } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { CONFIRM_BADGE } from './_shared';

const SHIFT_TYPES = ['Morning', 'Afternoon', 'Evening', 'Night'];
const CONF_STATUSES = ['Not Confirmed', 'Pending', 'Confirmed', 'Declined', 'No Response'];
const CONF_METHODS = ['Call', 'Text', 'Call + Text'];
const SHIFT_STATUSES = ['Not Started', 'Check-in', 'Checkout', 'Late Clock In', 'Early Clock Out', 'Late Clock Out', 'Absent', 'Completed', 'Cancelled'];

const emptyFilters = {
  officer_id: '', vendor_id: '', client_id: '', post_site_id: '', post_pin: '',
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
  const canHistory = hasPermission(user, 'dispatch.confirmation.history');

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
  const [historyDialog, setHistoryDialog] = useState(null);
  const [history, setHistory] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const { data } = await api.get('/dispatch/schedules', { params });
      setRows(data.items || []);
      setTotal(data.total || 0);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [page, limit, filters]);

  useEffect(() => { load(); }, [load]);
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
  const openEdit = (row) => { setEditing(row); setForm({ ...row }); setDialogOpen(true); };

  const submit = async () => {
    // client-side required check
    for (const k of ['date', 'shift_type', 'start_time', 'end_time', 'client_id', 'vendor_id', 'post_site_id', 'officer_id']) {
      if (!form[k]) { toast.error(`${k.replace('_', ' ')} is required`); return; }
    }
    try {
      if (editing) await api.put(`/dispatch/schedules/${editing.id}`, form);
      else await api.post('/dispatch/schedules', form);
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

  const openConfirm = (row) => { setConfDialog(row); setConfForm({ confirmation_status: 'Confirmed', confirmation_method: 'Call', remarks: '' }); };
  const submitConfirm = async () => {
    try {
      await api.post(`/dispatch/schedules/${confDialog.id}/confirm`, confForm);
      toast.success('Confirmation updated'); setConfDialog(null); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const openHistory = async (row) => {
    setHistoryDialog(row);
    try { const { data } = await api.get(`/dispatch/schedules/${row.id}/history`); setHistory(data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
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

      {/* Filters */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold"><Filter className="w-4 h-4" /> Filters</div>
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
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => { setFilters(emptyFilters); setPage(1); }} data-testid="clear-filters">
            Clear filters
          </Button>
          {activeChips.map(({ k, v }) => (
            <span key={k} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-xs">
              {k.replace('_', ' ')}: {v.slice(0, 16)}
              <button onClick={() => setF(k, '')}><X className="w-3 h-3" /></button>
            </span>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-3 py-3">Date</th><th className="px-3 py-3">Officer</th>
              <th className="px-3 py-3">Post Pin</th><th className="px-3 py-3">Post Site</th>
              <th className="px-3 py-3">Client</th><th className="px-3 py-3">Vendor</th>
              <th className="px-3 py-3">Shift</th><th className="px-3 py-3">Time</th>
              <th className="px-3 py-3">Hours</th>
              {canFinancial && <><th className="px-3 py-3">Duty Rate</th><th className="px-3 py-3">Billing</th></>}
              <th className="px-3 py-3">Confirmation</th><th className="px-3 py-3">Status</th>
              <th className="px-3 py-3 text-right">Actions</th>
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
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${CONFIRM_BADGE[r.confirmation_status] || 'bg-slate-100 text-slate-600'}`}>{r.confirmation_status}</span>
                </td>
                <td className="px-3 py-2 text-xs">{r.shift_status}</td>
                <td className="px-3 py-2 text-right space-x-1 whitespace-nowrap">
                  {canConfirm && <Button size="sm" variant="outline" onClick={() => openConfirm(r)} data-testid={`confirm-${r.id}`}><Phone className="w-3 h-3" /></Button>}
                  {canHistory && <Button size="sm" variant="outline" onClick={() => openHistory(r)} data-testid={`history-${r.id}`}><History className="w-3 h-3" /></Button>}
                  {canEdit && <Button size="sm" variant="outline" onClick={() => openEdit(r)} data-testid={`edit-${r.id}`}>Edit</Button>}
                  {canCancel && r.shift_status !== 'Cancelled' && <Button size="sm" variant="outline" onClick={() => cancelSchedule(r)}>Cancel</Button>}
                  {canDelete && <Button size="sm" variant="outline" onClick={() => deleteSchedule(r)}>Del</Button>}
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
          <DialogHeader><DialogTitle>{editing ? 'Edit' : 'New'} Dispatch Schedule</DialogTitle></DialogHeader>
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
          <DialogHeader><DialogTitle>Update Confirmation</DialogTitle></DialogHeader>
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

      {/* History dialog */}
      <Dialog open={!!historyDialog} onOpenChange={(o) => !o && setHistoryDialog(null)}>
        <DialogContent className="max-w-lg max-h-[70vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Confirmation History</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {history.length === 0 ? <p className="text-sm text-[#64748B]">No history yet.</p>
              : history.map(h => (
                <div key={h.id} className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{h.contacted_by_name}</span>
                    <span className="text-xs text-[#64748B]">{h.contacted_at?.slice(0, 16).replace('T', ' ')}</span>
                  </div>
                  <div className="text-xs text-[#64748B] mt-1">{h.contacted_by_role} · {h.method || '—'}</div>
                  <div className="mt-1"><span className={`px-2 py-0.5 rounded-full text-xs ${CONFIRM_BADGE[h.status] || 'bg-slate-100'}`}>{h.status}</span></div>
                  {h.remarks && <div className="text-sm mt-2 text-[#334155] dark:text-[#E4E4E7]">{h.remarks}</div>}
                </div>
              ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DispatchSchedulePage;
