# OfficeFlow - Enterprise SaaS PRD

## Original Problem Statement
Production-ready enterprise SaaS "OfficeFlow" — Office / HR / Employee / Attendance / GPS / Task management. Linear / Notion / Stripe aesthetic. **Single-company** deployment. Bangladesh-first (BDT + Asia/Dhaka).

### Extension (Feb 2026)
Extend OfficeFlow with a complete **Dispatch Management System** for security-guard dispatch operations: Clients, Vendors, Security Officers, Post Sites, Dispatch Schedules with conflict-detection and confirmation workflow, all guarded by a granular permission system. No GPS on external entities.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor) + httpx (Nominatim geocode)
- **Frontend**: React 19 + Tailwind + shadcn/ui + Framer Motion + Zustand
- **Auth**: JWT httpOnly cookies. Public sign-up disabled.
- **Permissions**: fine-grained code-based ACL layered on top of role; super_admin bypasses all; hd bypasses all dispatch.*.
- **Storage**: Emergent Object Storage
- **Maps**: React-Leaflet + OpenStreetMap tiles (existing employee GPS only)
- **Timezone**: Asia/Dhaka default
- **Currency**: BDT default

## Personas
Super Admin, Admin, HR, Manager, **HD (Head of Dispatch — full Dispatch access)**, Employee.

## Implemented

### Backend
- **Existing (unchanged)**: Auth, Employees (with permissions[]), Attendance multi-session, GPS start/stop, Leaves, Work Shifts + Bulk Assign, Overtime queue, Payroll auto-calc + branded PDF + Resend auto-email, Notifications, App Settings, Office Locations (Nominatim geocode), Reports.
- **New – Dispatch Module** (`routes/dispatch.py`):
  - Permission infrastructure (`utils/permissions.py`) — 25 permission codes across dashboard/schedule/clients/vendors/officers/post_sites/confirmation/reports/financial/audit
  - `/api/dispatch/clients` — CRUD + soft delete
  - `/api/dispatch/vendors` — CRUD + soft delete
  - `/api/dispatch/officers` — CRUD + 5 statuses (active/inactive/suspended/terminated/on_leave), no GPS
  - `/api/dispatch/post-sites` — CRUD, unique post_pin enforced, no GPS
  - `/api/dispatch/schedules` — CRUD + cancel + delete with:
    - auto-computed `duty_hours` (overnight-aware, backend-authoritative)
    - officer overlap conflict detection (409)
    - server-side filters: officer, vendor, client, post_site, post_pin (regex), date range, shift_type, confirmation_status, shift_status
    - server-side pagination (50/100/250)
    - financial fields (duty_rate/billing_rate/work_order_number) stripped from responses without `dispatch.financial.view`
  - `/api/dispatch/schedules/{id}/confirm` + append-only `dispatch_confirmation_history`
  - `/api/dispatch/dashboard/stats` — today's totals, open positions, directory counts
  - Compound MongoDB indexes for hot query paths

### Frontend
- **Existing (unchanged)**: Branded Login, Dashboard, Employees, Attendance, Live Map, GPS Share, Work Shifts + Bulk Assign, Overtime, Leaves, Calendar, Payroll (PDF), Reports, Settings.
- **New**:
  - `lib/permissions.js` — mirror of backend perm registry + hasPermission helper
  - `components/PermissionsSection.js` — collapsible perm-group UI with Select All/Clear All
  - Add/Edit Employee dialogs extended with Permissions section + HD role option
  - Sidebar shows a "DISPATCH" group filtered by permission (super_admin/hd see all)
  - `pages/dashboard/dispatch/*`:
    - `DispatchDashboardPage` — 12 KPI cards
    - `DispatchSchedulePage` — full CRUD, 10-way filter row, chips, pagination, conflict-aware form, financial-permission-aware columns, confirmation flow + history dialog
    - `EntityCrudPage` (generic) → `ClientsPage`, `VendorsPage`, `OfficersPage`, `PostSitesPage`
    - Today's Dispatch = schedule page pre-filtered to today
  - Routes registered under `/dashboard/dispatch/*`

## Changelog
- **2026-02 (iter 17)**: **Dispatch Reports + Role Restriction + Dispatch Calendar** — 5 report endpoints (schedules + by-officer/post/client/vendor) with 3-month cap and permission-aware CSV/PDF export; only super_admin may create or promote to `hd`/`super_admin`; new Calendar page with Day/Week/Month views and click-through details. 13/13 backend + 100% frontend functional tests passed.
- **2026-02 (iter 14)**: **Dispatch Management System** — permission infrastructure, Clients/Vendors/Officers/Post Sites CRUD, Dispatch Schedule with filters + pagination + officer conflict detection, confirmation flow with append-only history, dashboard stats, financial-field response redaction, HD role bypass. 22/23 backend tests pass; the one create-response permission bug was fixed same-iteration.
- **2026-02 (iter 12)**: Office address auto-geocoding via Nominatim. Bulk Shift Assign.
- **2026-02 (iter 10)**: Removed Companies, Reports menu, LiveMap office markers, Employee Edit dialog.
- **2026-02 (iter 9)**: Multi-session attendance, Office Locations, Payslip email, Employee GPS Share.

## Prioritized Backlog

### P1 (next iteration)
- Dispatch Calendar (Day/Week/Month with FullCalendar-style event grid)
- Open Posts finder (list unfilled positions + suggest available active officers)
- Dispatch Reports page (Officer/Post Site/Client/Vendor reports + 3-month cap + CSV/PDF export respecting financial perms)
- Audit logging on all Dispatch write actions (extends existing pattern)
- Dispatch WebSocket notifications for confirmation status changes

### P2
- Restrict role assignment: prevent non-super-admins from creating `hd`/`super_admin` accounts
- Post Site → officer picker filtered by vendor
- Auto Check-in when employee GPS enters office geofence
- Monthly Payroll Batch (one-click for all active employees)
- Documents module, Announcements, 2FA, i18n

### P3
- Activity logs UI, real-time officer status board, mobile PWA install
