# OfficeFlow - Enterprise SaaS PRD

## Original Problem Statement
Production-ready enterprise SaaS "OfficeFlow" — Office / HR / Employee / Attendance / GPS / Task management. Linear / Notion / Stripe aesthetic. **Single-company** deployment. Bangladesh-first (BDT + Asia/Dhaka).

## Architecture
- **Backend**: FastAPI + MongoDB (Motor) + httpx (Nominatim geocode)
- **Frontend**: React 19 + Tailwind + shadcn/ui + Framer Motion + Zustand
- **Auth**: JWT httpOnly cookies. Public sign-up disabled.
- **Storage**: Emergent Object Storage
- **Maps**: React-Leaflet + OpenStreetMap tiles; Nominatim geocode
- **PDF**: reportlab
- **Email**: Resend (payslip auto-email)
- **Timezone**: Asia/Dhaka default
- **Currency**: BDT default

## Personas
Super Admin, Admin, HR, Manager, Employee.

## Implemented
### Backend
- Auth, Employees (create/**edit** with password + status/salary/role/dept + delete), Attendance multi-session, GPS start/stop, Leaves
- Work Shifts (timezone-aware) + Shift Comments + **Bulk Assign endpoint** (skips overlaps, notifies employees)
- Overtime queue, Payroll auto-calc + branded PDF + Resend auto-email
- Notifications
- App Settings (brand+logo+login copy+currency+timezone)
- **Office Locations** — CRUD + nearest with haversine + **address-only creation via Nominatim geocoding** + /geocode endpoint
- **Reports** — summary/attendance/payroll/overtime (manager+ RBAC)

### Frontend
- Branded Login page, Dashboard, Employees (Add + Edit dialog)
- Attendance (multi-session, nearest office banner)
- Live Map + office markers + geofence circles
- GPS Share Location
- Work Shifts + chat + **Bulk Assign dialog** with employee multi-select + shift template
- Overtime, Leaves, Calendar
- Payroll (currency, PDF)
- **Reports page** with Overview + Attendance/Payroll/Overtime tabs + CSV export
- Settings tabs (Profile / Notifications / Security / Appearance / **Branding** / **Offices** with Find-on-map)
- Global LocationStreamer, dark/light theme

## Changelog
- **2026-02 (iter 12)**: Office address auto-geocoding via Nominatim (no more forced lat/lng). Bulk Shift Assign (many employees, one template, overlap-skip). Verified Reports page rendering.
- **2026-02 (iter 10)**: Removed Companies, Reports menu, LiveMap office markers, Employee Edit dialog.
- **2026-02 (iter 9)**: Multi-session attendance, Office Locations, Payslip email, Employee GPS Share.
- **2026-02 (iter 8)**: Currency+timezone+branding settings, Add Employee dialog, PDF payslip.
- **2026-02 (iter 7)**: Auth cookie fix, prod CORS, Shift Comments, Overtime queue.

## Prioritized Backlog

### P1
- Auto Check-in when GPS enters office geofence
- Payslip email status badge on Payroll rows
- Monthly Payroll Batch (one-click for all active employees)
- Reports monthly PDF export (per-employee)

### P2
- Projects, Announcements, Documents, 2FA
- Bulk shift edit / delete
- Auto-suspend employees inactive > N days

### P3
- Activity logs, WebSocket notifications, i18n
