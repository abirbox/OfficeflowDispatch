import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { useTheme } from '@/contexts/ThemeContext';
import {
  LayoutDashboard,
  Users,
  Building2,
  MapPin,
  CheckSquare,
  FolderKanban,
  Calendar,
  FileText,
  DollarSign,
  Settings,
  LogOut,
  Menu,
  X,
  Sun,
  Moon,
  Bell,
  Search,
  ChevronDown,
  TrendingUp,
  BarChart3,
  Truck,
  Shield,
  ClipboardList,
} from 'lucide-react';
import { hasPermission, hasAnyDispatchPerm } from '@/lib/permissions';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import NotificationBell from '@/components/NotificationBell';
import LocationStreamer from '@/components/LocationStreamer';
import { useAppSettings } from '@/contexts/AppSettingsContext';

const allNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
  { name: 'My Shifts', href: '/dashboard/shifts', icon: FolderKanban, roles: ['employee'] },
  { name: 'My Overtime', href: '/dashboard/overtime', icon: TrendingUp, roles: ['employee'] },
  { name: 'My Attendance', href: '/dashboard/attendance', icon: CheckSquare, roles: ['employee'] },
  { name: 'Share Location', href: '/dashboard/gps', icon: MapPin, roles: ['employee'] },
  { name: 'My Payroll', href: '/dashboard/payroll', icon: DollarSign, roles: ['employee'] },
  { name: 'My Leaves', href: '/dashboard/leaves', icon: FileText, roles: ['employee'] },
  { name: 'Employees', href: '/dashboard/employees', icon: Users, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Work Shifts', href: '/dashboard/shifts', icon: FolderKanban, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Overtime', href: '/dashboard/overtime', icon: TrendingUp, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Attendance', href: '/dashboard/attendance', icon: CheckSquare, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Live Map', href: '/dashboard/live-map', icon: MapPin, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Calendar', href: '/dashboard/calendar', icon: Calendar, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
  { name: 'Leaves', href: '/dashboard/leaves', icon: FileText, roles: ['super_admin', 'admin', 'hr'] },
  { name: 'Payroll', href: '/dashboard/payroll', icon: DollarSign, roles: ['super_admin', 'admin', 'hr'] },
  { name: 'Reports', href: '/dashboard/reports', icon: BarChart3, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
];

const dispatchNavigation = [
  { name: 'Dispatch Dashboard', href: '/dashboard/dispatch', icon: LayoutDashboard, perm: 'dispatch.dashboard.view' },
  { name: "Today's Dispatch", href: '/dashboard/dispatch/today', icon: ClipboardList, perm: 'dispatch.schedule.view' },
  { name: 'Dispatch Schedule', href: '/dashboard/dispatch/schedules', icon: Truck, perm: 'dispatch.schedule.view' },
  { name: 'Clients', href: '/dashboard/dispatch/clients', icon: Building2, perm: 'dispatch.clients.view' },
  { name: 'Vendors', href: '/dashboard/dispatch/vendors', icon: Building2, perm: 'dispatch.vendors.view' },
  { name: 'Security Officers', href: '/dashboard/dispatch/officers', icon: Shield, perm: 'dispatch.officers.view' },
  { name: 'Post Sites', href: '/dashboard/dispatch/post-sites', icon: MapPin, perm: 'dispatch.post_sites.view' },
];

const DashboardLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const { settings } = useAppSettings();
  const brandName = settings?.brand_name || 'OfficeFlow';
  const navigate = useNavigate();
  const location = useLocation();

  const userRole = user?.role || 'employee';
  const navigation = allNavigation.filter((item) => item.roles.includes(userRole));
  const dispatchNav = hasAnyDispatchPerm(user)
    ? dispatchNavigation.filter((item) => hasPermission(user, item.perm))
    : [];

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#09090B]">
      {/* Desktop Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width: sidebarOpen ? 256 : 64,
        }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="fixed left-0 top-0 h-full bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 hidden lg:block"
        data-testid="dashboard-sidebar"
      >
        <div className="h-full flex flex-col">
          {/* Logo */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-[#E2E8F0] dark:border-[#27272A]">
            <AnimatePresence mode="wait">
              {sidebarOpen ? (
                <motion.h1
                  key="logo-full"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight"
                  data-testid="app-logo"
                >
                  {brandName}
                </motion.h1>
              ) : (
                <motion.div
                  key="logo-icon"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="w-8 h-8 bg-[#4F46E5] rounded-lg"
                />
              )}
            </AnimatePresence>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-[#64748B] hover:text-[#0F172A] dark:text-[#A1A1AA] dark:hover:text-[#FAFAFA]"
              data-testid="sidebar-toggle"
            >
              <Menu className="w-5 h-5" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-3 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <button
                  key={item.name}
                  onClick={() => navigate(item.href)}
                  data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                    active
                      ? 'bg-[#4F46E5] text-white'
                      : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
                  }`}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <AnimatePresence>
                    {sidebarOpen && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-sm font-medium"
                      >
                        {item.name}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              );
            })}
            {dispatchNav.length > 0 && (
              <>
                <div className="mt-4 mb-1 px-3 text-xs uppercase tracking-wider text-[#94A3B8] dark:text-[#71717A]">
                  {sidebarOpen ? 'Dispatch' : ''}
                </div>
                {dispatchNav.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <button
                      key={item.name}
                      onClick={() => navigate(item.href)}
                      data-testid={`nav-${item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                        active ? 'bg-[#4F46E5] text-white'
                          : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
                      }`}
                    >
                      <Icon className="w-5 h-5 flex-shrink-0" />
                      <AnimatePresence>
                        {sidebarOpen && (
                          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm font-medium">
                            {item.name}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </button>
                  );
                })}
              </>
            )}
          </nav>

          {/* User Profile */}
          <div className="p-3 border-t border-[#E2E8F0] dark:border-[#27272A]">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] transition-colors"
                  data-testid="user-menu-trigger"
                >
                  <Avatar className="w-8 h-8">
                    <AvatarImage src={user?.avatar_path} />
                    <AvatarFallback className="bg-[#4F46E5] text-white text-sm">
                      {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  {sidebarOpen && (
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA] truncate">
                        {user?.name}
                      </p>
                      <p className="text-xs text-[#64748B] dark:text-[#A1A1AA] truncate">
                        {user?.role}
                      </p>
                    </div>
                  )}
                  {sidebarOpen && <ChevronDown className="w-4 h-4 text-[#64748B] dark:text-[#A1A1AA]" />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate('/dashboard/profile')}>
                  Profile Settings
                </DropdownMenuItem>
                <DropdownMenuItem onClick={toggleTheme}>
                  {theme === 'light' ? <Moon className="w-4 h-4 mr-2" /> : <Sun className="w-4 h-4 mr-2" />}
                  {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} data-testid="logout-button">
                  <LogOut className="w-4 h-4 mr-2" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </motion.aside>

      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-white dark:bg-[#18181B] border-b border-[#E2E8F0] dark:border-[#27272A] z-30 flex items-center justify-between px-4">
        <h1 className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{brandName}</h1>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          data-testid="mobile-menu-toggle"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </Button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            className="lg:hidden fixed inset-y-0 left-0 w-64 bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 pt-16"
          >
            <nav className="p-3 space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <button
                    key={item.name}
                    onClick={() => {
                      navigate(item.href);
                      setMobileMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                      active
                        ? 'bg-[#4F46E5] text-white'
                        : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A]'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-sm font-medium">{item.name}</span>
                  </button>
                );
              })}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main
        className="transition-all duration-300"
        style={{
          marginLeft: sidebarOpen ? '256px' : '64px',
        }}
      >
        <div className="lg:ml-0 ml-0 pt-16 lg:pt-0">
          {/* Top Bar */}
          <div className="h-16 bg-white/70 dark:bg-[#18181B]/70 backdrop-blur-xl border-b border-[#E2E8F0] dark:border-[#27272A] px-6 flex items-center justify-between">
            <div className="flex-1 max-w-2xl">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                <Input
                  placeholder="Search..."
                  className="pl-11 bg-[#F8FAFC] dark:bg-[#09090B] border-[#E2E8F0] dark:border-[#27272A]"
                  data-testid="global-search-input"
                />
              </div>
            </div>

            <div className="hidden lg:flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                data-testid="theme-toggle-button"
              >
                {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              </Button>
              <Button variant="ghost" size="icon" data-testid="notifications-button-old" className="hidden">
                <Bell className="w-5 h-5" />
              </Button>
              <NotificationBell />
            </div>
          </div>

          {/* Page Content */}
          <div className="p-6">
            <Outlet />
          </div>
        </div>
      </main>
      <LocationStreamer />
    </div>
  );
};

export default DashboardLayout;