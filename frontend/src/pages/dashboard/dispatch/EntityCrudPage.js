import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { Plus, Pencil, Trash2, Search } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { STATUS_BADGE } from './_shared';

/**
 * Generic entity CRUD table used by Clients, Vendors, Officers, Post Sites.
 *   props.title, props.endpoint (e.g. '/dispatch/clients'), props.permBase (e.g. 'dispatch.clients')
 *   props.fields — [{key,label,type?,options?,required?,select?:'clients'|'vendors'}]
 *   props.columns — [{key,label}]
 *   props.statuses — [{value,label}]  optional; default active/inactive
 */
const EntityCrudPage = ({ title, endpoint, permBase, fields, columns, statuses }) => {
  const { user } = useAuthStore();
  const canCreate = hasPermission(user, `${permBase}.create`);
  const canEdit = hasPermission(user, `${permBase}.edit`);
  const canDelete = hasPermission(user, `${permBase}.delete`);

  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [clients, setClients] = useState([]);
  const [vendors, setVendors] = useState([]);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(endpoint, { params: { search } });
      setRows(Array.isArray(data) ? data : (data.items || []));
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); }
  };
  useEffect(() => {
    load();
    if (fields.some((f) => f.select === 'clients')) api.get('/dispatch/clients').then(r => setClients(r.data));
    if (fields.some((f) => f.select === 'vendors')) api.get('/dispatch/vendors').then(r => setVendors(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const openCreate = () => { setEditing(null); setForm({ status: 'active' }); setDialogOpen(true); };
  const openEdit = (row) => { setEditing(row); setForm({ ...row }); setDialogOpen(true); };

  const submit = async () => {
    try {
      if (editing) await api.put(`${endpoint}/${editing.id}`, form);
      else await api.post(endpoint, form);
      toast.success(`${title.slice(0, -1)} ${editing ? 'updated' : 'created'}`);
      setDialogOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const remove = async (row) => {
    if (!window.confirm(`Deactivate "${row.name || row.post_pin}"?`)) return;
    try { await api.delete(`${endpoint}/${row.id}`); toast.success('Deactivated'); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const renderField = (f) => {
    if (f.select === 'clients')
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue placeholder="Select client" /></SelectTrigger>
          <SelectContent>{clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.select === 'vendors')
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue placeholder="Select vendor" /></SelectTrigger>
          <SelectContent>{vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.options)
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue /></SelectTrigger>
          <SelectContent>{f.options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.type === 'textarea')
      return <Textarea value={form[f.key] || ''} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} data-testid={`field-${f.key}`} />;
    return <Input type={f.type || 'text'} value={form[f.key] ?? ''} onChange={(e) => setForm({ ...form, [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value })} data-testid={`field-${f.key}`} />;
  };

  return (
    <div className="space-y-6" data-testid={`page-${permBase}`}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{title}</h1>
        {canCreate && (
          <Button onClick={openCreate} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="create-btn">
            <Plus className="w-4 h-4 mr-2" /> Add {title.slice(0, -1)}
          </Button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
          <Input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" data-testid="search-input" />
        </div>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              {columns.map((c) => <th key={c.key} className="px-4 py-3">{c.label}</th>)}
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={columns.length + 2} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={columns.length + 2} className="px-4 py-8 text-center text-[#64748B]">No records found</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id} data-testid={`row-${r.id}`}>
                {columns.map((c) => <td key={c.key} className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r[c.key] ?? '—'}</td>)}
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE[r.status] || STATUS_BADGE.inactive}`}>{r.status}</span>
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  {canEdit && <Button size="sm" variant="outline" onClick={() => openEdit(r)} data-testid={`edit-${r.id}`}><Pencil className="w-3 h-3" /></Button>}
                  {canDelete && <Button size="sm" variant="outline" onClick={() => remove(r)} data-testid={`delete-${r.id}`}><Trash2 className="w-3 h-3" /></Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing ? 'Edit' : 'Add'} {title.slice(0, -1)}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {fields.map((f) => (
              <div key={f.key} className={f.type === 'textarea' ? 'sm:col-span-2 space-y-1' : 'space-y-1'}>
                <Label>{f.label}{f.required && ' *'}</Label>
                {renderField(f)}
              </div>
            ))}
            {(statuses || [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]).length > 0 && (
              <div className="space-y-1">
                <Label>Status</Label>
                <Select value={form.status || 'active'} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger data-testid="field-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(statuses || [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]).map((s) =>
                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={submit} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-entity">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EntityCrudPage;
