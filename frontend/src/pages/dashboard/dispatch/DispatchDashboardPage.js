import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Users, Building2, MapPin, Shield, CheckCircle2, Clock, XCircle, AlertTriangle } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';

const Card = ({ icon: Icon, label, value, color, testid }) => (
  <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5" data-testid={testid}>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs uppercase tracking-wider text-[#64748B]">{label}</p>
        <p className="mt-2 text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{value ?? '—'}</p>
      </div>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
    </div>
  </div>
);

const DispatchDashboardPage = () => {
  const { user } = useAuthStore();
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/dispatch/dashboard/stats').then(({ data }) => setStats(data))
      .catch(() => setStats({}))
      .finally(() => setLoading(false));
  }, []);

  if (!hasPermission(user, 'dispatch.dashboard.view')) {
    return <div className="p-8 text-[#64748B]">You do not have permission to view the Dispatch dashboard.</div>;
  }

  return (
    <div className="space-y-6" data-testid="dispatch-dashboard">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Dispatch Dashboard</h1>
        <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1">Today's dispatch operations at a glance</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card icon={Clock} label="Today's Dispatch" value={loading ? '...' : stats.today_total} color="bg-indigo-600" testid="stat-today" />
        <Card icon={CheckCircle2} label="Confirmed" value={stats.confirmed} color="bg-emerald-600" testid="stat-confirmed" />
        <Card icon={Clock} label="Pending" value={stats.pending} color="bg-amber-500" testid="stat-pending" />
        <Card icon={AlertTriangle} label="No Response" value={stats.no_response} color="bg-slate-500" testid="stat-noresp" />
        <Card icon={XCircle} label="Declined" value={stats.declined} color="bg-rose-600" testid="stat-declined" />
        <Card icon={Clock} label="Late" value={stats.late} color="bg-orange-500" testid="stat-late" />
        <Card icon={XCircle} label="Absent" value={stats.absent} color="bg-rose-700" testid="stat-absent" />
        <Card icon={AlertTriangle} label="Open Positions" value={stats.open_positions} color="bg-fuchsia-600" testid="stat-open" />
      </div>

      <h2 className="text-lg font-semibold pt-4">Directory</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card icon={Building2} label="Clients" value={stats.clients} color="bg-sky-600" testid="stat-clients" />
        <Card icon={Building2} label="Vendors" value={stats.vendors} color="bg-teal-600" testid="stat-vendors" />
        <Card icon={Shield} label="Security Officers" value={stats.officers} color="bg-violet-600" testid="stat-officers" />
        <Card icon={MapPin} label="Post Sites" value={stats.post_sites} color="bg-cyan-600" testid="stat-posts" />
      </div>
    </div>
  );
};

export default DispatchDashboardPage;
