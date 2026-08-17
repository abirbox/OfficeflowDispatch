import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AppSettingsProvider } from "@/contexts/AppSettingsContext";
import { Toaster } from "@/components/ui/sonner";
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardLayout from "@/layouts/DashboardLayout";
import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";
import ForgotPassword from "@/pages/auth/ForgotPassword";
import ResetPassword from "@/pages/auth/ResetPassword";
import DashboardHome from "@/pages/dashboard/DashboardHome";
import CompaniesPage from "@/pages/dashboard/CompaniesPage";  // legacy — hidden from nav
import EmployeesPage from "@/pages/dashboard/EmployeesPage";
import EmployeeDetailPage from "@/pages/dashboard/EmployeeDetailPage";
import AttendancePage from "@/pages/dashboard/AttendancePage";
import GPSTrackingPage from "@/pages/dashboard/GPSTrackingPage";
import LiveMapPage from "@/pages/dashboard/LiveMapPage";
import TasksPage from "@/pages/dashboard/TasksPage";
import ShiftsPage from "@/pages/dashboard/ShiftsPage";
import OvertimePage from "@/pages/dashboard/OvertimePage";
import ReportsPage from "@/pages/dashboard/ReportsPage";
import CalendarPage from "@/pages/dashboard/CalendarPage";
import LeavesPage from "@/pages/dashboard/LeavesPage";
import PayrollPage from "@/pages/dashboard/PayrollPage";
import SettingsPage from "@/pages/dashboard/SettingsPage";
import DispatchDashboardPage from "@/pages/dashboard/dispatch/DispatchDashboardPage";
import DispatchSchedulePage from "@/pages/dashboard/dispatch/DispatchSchedulePage";
import { ClientsPage, VendorsPage, OfficersPage, PostSitesPage } from "@/pages/dashboard/dispatch/EntityPages";
import "@/App.css";

function App() {
  return (
    <ThemeProvider>
      <AppSettingsProvider>
        <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Navigate to="/login" replace />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardHome />} />
            <Route path="employees" element={<EmployeesPage />} />
            <Route path="employees/:id" element={<EmployeeDetailPage />} />
            <Route path="companies" element={<CompaniesPage />} />
            <Route path="attendance" element={<AttendancePage />} />
            <Route path="gps" element={<GPSTrackingPage />} />
            <Route path="live-map" element={<LiveMapPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="shifts" element={<ShiftsPage />} />
            <Route path="overtime" element={<OvertimePage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="leaves" element={<LeavesPage />} />
            <Route path="payroll" element={<PayrollPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="dispatch" element={<DispatchDashboardPage />} />
            <Route path="dispatch/schedules" element={<DispatchSchedulePage />} />
            <Route path="dispatch/today" element={<DispatchSchedulePage todayOnly />} />
            <Route path="dispatch/clients" element={<ClientsPage />} />
            <Route path="dispatch/vendors" element={<VendorsPage />} />
            <Route path="dispatch/officers" element={<OfficersPage />} />
            <Route path="dispatch/post-sites" element={<PostSitesPage />} />
          </Route>
        </Routes>
        <Toaster />
        </BrowserRouter>
      </AppSettingsProvider>
    </ThemeProvider>
  );
}

export default App;
