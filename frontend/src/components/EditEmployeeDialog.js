import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/sonner';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { UserCog, KeyRound, Ban, Trash2, CheckCircle2 } from 'lucide-react';

const ROLES = [
  { value: 'employee', label: 'Employee' },
  { value: 'manager', label: 'Manager' },
  { value: 'hr', label: 'HR' },
  { value: 'admin', label: 'Admin' },
];

const EditEmployeeDialog = ({ open, onOpenChange, employee, onChanged }) => {
  const [form, setForm] = useState(null);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    if (employee && open) {
      setForm({
        name: employee.name || '',
        phone: employee.phone || '',
        role: employee.role || 'employee',
        department: employee.department_name || '',
        salary: employee.salary || 0,
        status: employee.status || 'active',
      });
      setPassword('');
    }
  }, [employee, open]);

  if (!employee || !form) return null;

  const save = async () => {
    setBusy('save');
    try {
      const payload = {
        name: form.name,
        phone: form.phone || null,
        role: form.role,
        salary: form.salary ? Number(form.salary) : null,
        status: form.status,
      };
      if (password && password.length >= 6) payload.password = password;
      await api.put(`/employees/${employee.id}`, payload);
      toast.success('Employee updated');
      onChanged?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(null); }
  };

  const suspend = async () => {
    setBusy('suspend');
    try {
      const newStatus = form.status === 'suspended' ? 'active' : 'suspended';
      await api.put(`/employees/${employee.id}`, { status: newStatus });
      toast.success(newStatus === 'suspended' ? 'Employee suspended' : 'Employee reactivated');
      onChanged?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(null); }
  };

  const remove = async () => {
    if (!window.confirm(`Deactivate ${employee.name}? They will lose access but the record stays for payroll history.`)) return;
    setBusy('delete');
    try {
      await api.delete(`/employees/${employee.id}`);
      toast.success('Employee deactivated');
      onChanged?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(null); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="edit-employee-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><UserCog className="w-5 h-5" /> Edit {employee.name}</DialogTitle>
          <DialogDescription>{employee.email}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label>Full Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="edit-emp-name" /></div>
            <div className="space-y-1"><Label>Phone</Label><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="edit-emp-phone" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Role</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="edit-emp-role"><SelectValue /></SelectTrigger>
                <SelectContent>{ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label>Department</Label><Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} data-testid="edit-emp-department" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label>Monthly Salary</Label><Input type="number" value={form.salary} onChange={(e) => setForm({ ...form, salary: e.target.value })} data-testid="edit-emp-salary" /></div>
            <div className="space-y-1">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger data-testid="edit-emp-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#27272A]">
            <Label className="flex items-center gap-2"><KeyRound className="w-4 h-4" /> Change Password (optional, min 6 chars)</Label>
            <Input type="text" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Leave empty to keep current password" data-testid="edit-emp-password" className="mt-1" />
          </div>
        </div>
        <DialogFooter className="flex-col sm:flex-row gap-2">
          <div className="flex gap-2 flex-1">
            <Button variant="outline" onClick={suspend} disabled={busy !== null} data-testid="suspend-employee-button">
              {form.status === 'suspended' ? <><CheckCircle2 className="w-4 h-4 mr-1" /> Reactivate</> : <><Ban className="w-4 h-4 mr-1" /> Suspend</>}
            </Button>
            <Button variant="outline" onClick={remove} disabled={busy !== null} className="text-red-600 border-red-200 hover:bg-red-50" data-testid="delete-employee-button">
              <Trash2 className="w-4 h-4 mr-1" /> Delete
            </Button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy !== null} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-employee-button">
              {busy === 'save' ? 'Saving…' : 'Save Changes'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default EditEmployeeDialog;
