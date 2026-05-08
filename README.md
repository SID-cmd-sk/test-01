# SR Manager Enterprise 2026

A modern enterprise desktop ERP platform for service request management, field operations, pipeline automation, and team communication.

Built with **PyQt6** + **Supabase** + **Microsoft Login**.

---

## Architecture

```
LOCAL JSON  ←→  SYNC ENGINE  ←→  SUPABASE (cloud DB)
    ↑                                      ↑
 All writes                         Multi-device access
 (fast, offline)                    (cloud mirror)

MICROSOFT LOGIN → Azure AD → Local user record → Role + Permissions
```

**Key design principle:** Local JSON is the primary write surface. All creates and updates go to `data/master_data.json` first, marked `_dirty=True`. The sync engine pushes dirty records to Supabase when internet is available. This keeps the app fully functional offline.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Supabase URL and key
```

### 3. Set up Supabase (Phase 2)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor → New Query**
3. Paste and run `setup/supabase_schema.sql`
4. Copy your **Project URL** and **Service Role Key** (Settings → API)
5. Add them to `.env` or Admin Settings → Cloud Sync

### 4. Run the app

```bash
python main.py
```

On first launch, a **setup dialog** appears. Enter your admin name, email, and password. This is your master admin account — it cannot be deleted.

---

## Microsoft Login Setup (Phase 3)

1. Go to [Azure Portal → App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps)
2. Click **New Registration**
3. Set **Redirect URI** → `http://localhost` (Mobile/Desktop platform)
4. Copy the **Application (Client) ID**
5. In SR Manager: Admin Settings → Microsoft Login → paste Client ID
6. Set Tenant ID: use `common` for personal + work accounts, or your org's tenant ID for company-only

---

## Role System

| Role          | Access                                               |
|---------------|------------------------------------------------------|
| MASTER_ADMIN  | Everything — cannot be deleted or deactivated        |
| ADMIN         | Full system access, user management, settings        |
| MANAGER       | All SRs, assign, close, reports                      |
| TECHNICAL     | Own SRs, status updates, pipeline steps              |
| VIEWER        | Read-only access (default for new Microsoft Login users) |

Custom roles with granular permissions can be created in Admin → Role Builder.

---

## Project Structure

```
main.py                        # Entry point, first-run setup, main window
db.py                          # Local storage CRUD client
requirements.txt
.env.example

services/
  supabase_service.py          # Phase 2: Supabase client + upsert/pull
  sync_service.py              # Phase 2: Push dirty records, pull cloud updates
  auth_service.py              # Phase 3: Microsoft MSAL login
  config_service.py            # Global settings (overdue_days now configurable)
  local_storage_service.py     # JSON storage engine (atomic writes, HMAC)
  encryption_service.py        # Machine-bound crypto, PBKDF2, Fernet backup
  pipeline_service.py          # SR workflow pipeline (advance/skip steps)
  backup_service.py            # Encrypted startup/shutdown/manual backups
  archive_service.py           # Yearly ZIP archive + dataset reset
  audit_service.py             # Async audit logging
  notification_service.py      # Desktop + in-app notifications
  search_service.py            # Global fuzzy search across all collections
  whatsapp_service.py          # QR Web + Meta Cloud API messaging
  email_service.py             # SMTP email with templates
  google_sheet_service.py      # Import/export Google Sheets and Excel
  stats_service.py             # SR analytics and productivity metrics
  scheduler.py                 # Daily WhatsApp report scheduler

ui/
  first_run_setup.py           # First-launch admin account wizard
  login.py                     # Login screen (email + Microsoft button)
  admin_dashboard.py           # Admin: Users, SRs, Pipeline, Roles, Stats
  manager_dashboard.py         # Manager: SRs, assign, reports
  technical_dashboard.py       # Tech: own SRs, pipeline steps
  admin_settings.py            # Branding, WhatsApp, Email, Cloud Sync config
  pipeline_builder.py          # Drag-build custom pipeline templates
  role_builder.py              # Visual permission editor
  stats_panel.py               # Charts and analytics

setup/
  supabase_schema.sql          # Run once in Supabase SQL Editor

cache/                         # Offline cache + MSAL token cache
backups/                       # Encrypted auto-backups
data/                          # master_data.json (local database)
```

---

## Sync Architecture

```
User makes a change (create SR, update status, etc.)
    ↓
local_storage.create/update_document() — marks record _dirty=True
    ↓
App continues immediately (no wait for network)
    ↓
User clicks "Sync Now" OR app triggers background sync
    ↓
SyncNowWorker (QThread) → sync_service.push_dirty_records()
    ↓
For each dirty record → supabase_service.upsert_document()
    ↓
On success → local_storage.mark_clean() → _dirty=False
On failure → record stays dirty → retried next sync
```

**Conflict resolution:** Cloud wins on pull. Local dirty records are never overwritten during a pull — they are pushed first. If a record is both locally dirty and newer in the cloud, the push will overwrite the cloud version (last-writer-wins per device).

---

## Building the EXE

```bash
# Install PyInstaller
pip install pyinstaller

# Build (Windows)
build_exe.bat

# Or manually:
pyinstaller --onefile --windowed --name "SR Manager Enterprise" main.py
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| App shows first-run setup every launch | `data/master_data.json` was deleted or corrupted. Restore from `backups/`. |
| Sync fails with "Not configured" | Add SUPABASE_URL and SUPABASE_KEY in Admin Settings → Cloud Sync |
| Microsoft login not available | Add AZURE_CLIENT_ID in Admin Settings → Microsoft Login |
| WhatsApp QR not loading | PyQt6-WebEngine not installed. Run `pip install PyQt6-WebEngine` |
| `supabase` module not found | Run `pip install supabase` |
| `msal` module not found | Run `pip install msal` |

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Done | Bug fixes: hardcoded admin, logout crash, settings path, configurable overdue |
| 2 | ✅ Done | Supabase integration, real sync engine, SQL schema |
| 3 | ✅ Done | Microsoft MSAL login, Azure AD, device-code flow |
| 4 | 🔲 Next | Missing services: notifications, search, media/attachments |
| 5 | 🔲 Planned | AI assistant (Claude API), voice notes, automation engine |
| 6 | 🔲 Planned | Multi-company, multi-language, form builder |
