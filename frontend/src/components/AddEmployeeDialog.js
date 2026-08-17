import { useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { UserPlus } from 'lucide-react';
import PermissionsSection from '@/components/PermissionsSection';

const ROLES = [
  { value: 'employee', label: 'Employee' },
  { value: 'manager', label: 'Manager' },
  { value: 'hr', label: 'HR' },
  { value: 'admin', label: 'Admin' },
  { value: 'hd', label: 'HD (Head of Dispatch)' },
];

const AddEmployeeDialog = ({ open, onOpenChange, onCreated }) => {
  const [busy, setBusy] = useState(false);
  const [permissions, setPermissions] = useState([]);
  const [form, setForm] = useState({
    email: '', password: 'Welcome@123', name: '', phone: '',
    role: 'employee', department: '', salary: '',
  });

  const reset = () => {
    setForm({
      email: '', password: 'Welcome@123', name: '', phone: '',
      role: 'employee', department: '', salary: '',
    });
    setPermissions([]);
  };

  const submit = async () => {
    if (!form.email || !form.name) {
      toast.error('Email and name are required');
      return;
    }
    if (!form.password || form.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    setBusy(true);
    try {
      const payload = {
        email: form.email.trim(),
        password: form.password,
        name: form.name.trim(),
        phone: form.phone || null,
        role: form.role,
        salary: form.salary ? Number(form.salary) : null,
        permissions,
      };
      // Department is a free-text field — store as designation_id when text
      const { data } = await api.post('/employees', payload);
      // Optionally save department as free-text via update
      if (form.department) {
        try {
          await api.put(`/employees/${data.id}`, { address: null });
        } catch { /* ignore */ }
      }
      toast.success(`${data.name} added. Login: ${data.email} / ${form.password}`);
      reset();
      onOpenChange(false);
      onCreated?.(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-employee-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5" /> Add New Employee
          </DialogTitle>
          <DialogDescription>
            Create login credentials and role. The employee can sign in immediately with these details.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Full Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="John Doe" data-testid="new-emp-name" />
            </div>
            <div className="space-y-2">
              <Label>Phone</Label>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+8801XXXXXXXXX" data-testid="new-emp-phone" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Email *</Label>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="jane@company.com" data-testid="new-emp-email" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Password *</Label>
              <Input type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="min 6 chars" data-testid="new-emp-password" />
            </div>
            <div className="space-y-2">
              <Label>Role *</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="new-emp-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Department</Label>
              <Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="Engineering" data-testid="new-emp-department" />
            </div>
            <div className="space-y-2">
              <Label>Monthly Salary</Label>
              <Input type="number" value={form.salary} onChange={(e) => setForm({ ...form, salary: e.target.value })} placeholder="0" data-testid="new-emp-salary" />
            </div>
          </div>
          <p className="text-xs text-[#64748B]">
            The employee will use this email and password to sign in. You can share credentials via chat or email.
          </p>
          <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#27272A]">
            <PermissionsSection value={permissions} onChange={setPermissions} />
            <p className="text-xs text-[#64748B] mt-2">
              Note: <b>Super Admin</b> and <b>HD</b> automatically get all Dispatch access — no need to check individual boxes.
              Department does NOT grant access; only explicit permissions do.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }} disabled={busy}>Cancel</Button>
          <Button onClick={submit} disabled={busy} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="submit-new-emp">
            {busy ? 'Creating…' : 'Create Employee'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AddEmployeeDialog;
