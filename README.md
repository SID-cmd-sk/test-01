
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║            SR MANAGER v2 — PRODUCTION READY DESKTOP APPLICATION             ║
║            Service Request Management System with Pipeline Support           ║
║                                                                              ║
║                         Built with PyQt6 + Firebase                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TABLE OF CONTENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   1.  What Is SR Manager v2?
   2.  System Requirements
   3.  Folder Structure
   4.  Step-by-Step Firebase Setup
   5.  Installation (Python Dependencies)
   6.  Creating the First Admin Account
   7.  How to Login (First Time)
   8.  Default Credentials
   9.  Role Overview & What Each Role Can Do
  10.  Admin God Panel — Full Guide
  11.  Manager Dashboard — Full Guide
  12.  Technical Dashboard — Full Guide
  13.  Pipeline / Approval Process — Full Guide
  14.  WhatsApp Setup (QR Mode)
  15.  WhatsApp Setup (Meta Cloud API Mode)
  16.  Email / SMTP Setup (Gmail)
  17.  Statistics Dashboard — Full Guide
  18.  Branding & Label Customisation
  19.  Running the Application
  20.  Building a Standalone EXE (No Python Required)
  21.  Firestore Collections Reference
  22.  Troubleshooting
  23.  Frequently Asked Questions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. WHAT IS SR MANAGER v2?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SR Manager v2 is a multi-user desktop application for managing Service
Requests across teams. It runs on Windows and connects to Firebase for
real-time cloud synchronisation.

KEY FEATURES:
  ✔  Three built-in roles: Admin, Manager, Technical
  ✔  Custom roles with granular permissions (Admin creates them)
  ✔  Pipeline / approval workflows — define multi-step processes per SR type
  ✔  WhatsApp notifications (QR scan mode — use your own number, no cost)
  ✔  WhatsApp notifications (Meta Cloud API mode — company number)
  ✔  Email notifications via Gmail SMTP
  ✔  Real-time sync across all connected machines (polls every 3 seconds)
  ✔  Live statistics dashboard with charts — trend, workload, overdue
  ✔  Technician availability shown when assigning SRs
  ✔  Full audit log of every action
  ✔  Admin can rename any label in the app (e.g. "SR" → "Work Order")
  ✔  Admin can change primary colour live
  ✔  Export all SRs to CSV
  ✔  Build as a standalone EXE — no Python needed on user machines


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2. SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅  Windows 10 or Windows 11 (64-bit)
  ✅  Python 3.10 or later
      Download: https://www.python.org/downloads/
      During install → tick "Add Python to PATH"

  ✅  Internet connection (Firebase requires internet)

  ✅  A Google account (for Firebase — free)

  NOTE: If you build the EXE using build_exe.bat, end users do NOT need
        Python installed. Only the developer machine needs Python.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  3. FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  sr_manager_v2/
  │
  ├── main.py                   ← Entry point. Run this to start the app.
  ├── firebase_client.py        ← Firebase Auth + Firestore REST client.
  │                               PUT YOUR API KEY AND PROJECT ID HERE.
  ├── requirements.txt          ← Python packages to install.
  ├── run_app.bat               ← Double-click to launch on Windows.
  ├── build_exe.bat             ← Build a standalone .exe (no Python needed).
  │
  ├── services/
  │   ├── config_service.py     ← Loads/saves global settings from Firestore.
  │   ├── pipeline_service.py   ← Pipeline template logic, step advance/skip.
  │   ├── stats_service.py      ← All statistics calculations.
  │   ├── audit_service.py      ← Writes audit log entries to Firestore.
  │   ├── whatsapp_service.py   ← WhatsApp (QR + Meta Cloud API).
  │   ├── email_service.py      ← Gmail SMTP email sender.
  │   └── scheduler.py          ← Daily report background scheduler.
  │
  ├── ui/
  │   ├── login.py              ← Login screen.
  │   ├── admin_dashboard.py    ← Admin 7-tab God Panel.
  │   ├── admin_settings.py     ← Global settings (branding, WA, email, etc).
  │   ├── pipeline_builder.py   ← Admin pipeline template editor.
  │   ├── role_builder.py       ← Admin role & permission editor.
  │   ├── stats_panel.py        ← Statistics charts (works for all roles).
  │   ├── manager_dashboard.py  ← Manager SR management + availability.
  │   ├── technical_dashboard.py← Technical SR view + pipeline step actions.
  │   └── whatsapp_qr_widget.py ← Embedded WhatsApp Web QR scanner.
  │
  └── utils/
      ├── auth.py               ← Session management, permission checking.
      └── helpers.py            ← Formatting, validation, stylesheet builder.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  4. STEP-BY-STEP FIREBASE SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You only do this ONCE. It takes about 10 minutes.

────────────────────────────────────
STEP 1 — Create a Firebase Project
────────────────────────────────────
  1. Open your browser and go to:
     https://console.firebase.google.com/

  2. Click "Add Project" (or "Create a project").

  3. Enter a project name — e.g. "sr-manager-company".

  4. When asked about Google Analytics → click "Continue" or disable it.
     (Analytics is not needed for this app.)

  5. Click "Create Project" and wait for it to finish.

  6. Click "Continue".

────────────────────────────────────
STEP 2 — Enable Email/Password Login
────────────────────────────────────
  1. In the Firebase Console left menu → click "Authentication".

  2. Click "Get started".

  3. Under "Sign-in providers" → click "Email/Password".

  4. Toggle "Enable" to ON.

  5. Click "Save".

────────────────────────────────────
STEP 3 — Create the Firestore Database
────────────────────────────────────
  1. In the Firebase Console left menu → click "Firestore Database".

  2. Click "Create database".

  3. Choose "Start in production mode".
     (We will set rules in the next step.)

  4. Select a Cloud Firestore location closest to you
     (e.g. asia-south1 for India, europe-west1 for Europe,
      us-central1 for USA).

  5. Click "Enable" and wait.

────────────────────────────────────
STEP 4 — Set Firestore Security Rules
────────────────────────────────────
  1. In Firestore → click the "Rules" tab at the top.

  2. Replace ALL existing text with this:

      rules_version = '2';
      service cloud.firestore {
        match /databases/{database}/documents {
          match /{document=**} {
            allow read, write: if request.auth != null;
          }
        }
      }

  3. Click "Publish".

  This rule means: only logged-in users can read/write.
  Your app handles role checking — Firestore just requires authentication.

────────────────────────────────────
STEP 5 — Get Your API Key and Project ID
────────────────────────────────────
  1. Click the gear icon ⚙ next to "Project Overview" in the left menu.

  2. Click "Project settings".

  3. Scroll down to "Your apps".

  4. If no web app exists:
       a. Click the </> icon (Web).
       b. Enter any nickname (e.g. "sr-manager-web").
       c. Do NOT tick "Firebase Hosting".
       d. Click "Register app".
       e. Click "Continue to console".

  5. Under "Your apps" you will now see a firebaseConfig block like this:

       const firebaseConfig = {
         apiKey: "AIzaSy...",
         authDomain: "your-project.firebaseapp.com",
         projectId: "your-project-id",
         ...
       };

  6. COPY these two values:
       • apiKey        → starts with "AIzaSy..."
       • projectId     → your project name with numbers

────────────────────────────────────
STEP 6 — Put Your Keys Into the App
────────────────────────────────────
  1. Open the file:   sr_manager_v2/firebase_client.py

  2. Find lines 16 and 17 near the top:

       FIREBASE_API_KEY    = "AIzaSyA0zVKt6GgirSbH_gAWIoAffyu47VXEuDI"
       FIREBASE_PROJECT_ID = "srlog-7e429"

  3. Replace those values with YOUR keys:

       FIREBASE_API_KEY    = "AIzaSyYOUR_ACTUAL_KEY_HERE"
       FIREBASE_PROJECT_ID = "your-actual-project-id"

  4. Save the file.

  ⚠  IMPORTANT: These credentials give access to your Firebase project.
     Keep this file private. Do not share it publicly or on GitHub.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  5. INSTALLATION (PYTHON DEPENDENCIES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Open Command Prompt (press Windows key, type "cmd", press Enter).

  2. Navigate to the sr_manager_v2 folder:

       cd C:\path\to\sr_manager_v2

     (Replace the path with wherever you extracted the zip.)

  3. Run this command:

       pip install -r requirements.txt

  4. If you want WhatsApp QR mode (scan your own WhatsApp):

       pip install PyQt6-WebEngine

     (This is optional. If you use Meta Cloud API mode, skip this.)

  5. Wait for installation to complete. You will see "Successfully installed".


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  6. CREATING THE FIRST ADMIN ACCOUNT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The app needs at least one admin user in Firebase before anyone can log in.
You create this manually in the Firebase Console. Do this ONCE.

────────────────────────────────────
PART A — Create the Auth User
────────────────────────────────────
  1. Go to https://console.firebase.google.com/

  2. Select your project.

  3. Left menu → "Authentication" → "Users" tab.

  4. Click "Add user".

  5. Enter:
       Email:    admin@yourcompany.com
       Password: Admin@1234

     (You can use any email/password. Write them down — this is your login.)

  6. Click "Add user".

  7. You will see the new user appear in the table.
     COPY the "User UID" — it looks like: abc123XYZdef456

────────────────────────────────────
PART B — Create the Firestore User Document
────────────────────────────────────
  1. Left menu → "Firestore Database".

  2. Click "+ Start collection".

  3. Collection ID: users
     Click "Next".

  4. Document ID: PASTE the UID you copied in Part A.

  5. Add these fields one by one:
     (Click "Add field" for each)

     Field name      Type      Value
     ──────────────────────────────────────────
     uid             string    (paste the UID)
     email           string    admin@yourcompany.com
     name            string    System Admin
     role            string    admin
     whatsapp_number string    (leave blank for now)
     active          boolean   true
     created_at      string    2024-01-01T00:00:00+00:00

  6. Click "Save".

  ✅  Your admin account is now ready.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  7. HOW TO LOGIN (FIRST TIME)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Double-click run_app.bat
     OR open Command Prompt in the folder and run: python main.py

  2. The SR Manager login screen appears.

  3. Enter:
       Email:    admin@yourcompany.com
       Password: Admin@1234
       (or whatever you set in Step 6)

  4. Click "Sign In".

  5. You will be taken to the Admin Dashboard.

  That's it. You are now logged in as Admin (God Mode).


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  8. DEFAULT CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────────────────────┐
  │  There are NO pre-built default users.                          │
  │  YOU create the first admin as described in Step 6.            │
  │  Then admin creates all other users from inside the app.       │
  └─────────────────────────────────────────────────────────────────┘

  RECOMMENDED first-time setup credentials (change after first login):

    Email:    admin@yourcompany.com
    Password: Admin@1234
    Role:     admin

  ⚠  Change the admin password after your first login!
     Firebase Console → Authentication → click the user → Reset password.

  After logging in as admin, create other users:
    Admin Dashboard → Users tab → "+ Create User" button.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  9. ROLE OVERVIEW & WHAT EACH ROLE CAN DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────┬────────────────────────────────────────────────────────────┐
│ ROLE         │ WHAT THEY CAN DO                                           │
├──────────────┼────────────────────────────────────────────────────────────┤
│              │ • Everything below, plus:                                  │
│    ADMIN     │ • Access the 7-tab God Panel                               │
│   (God Mode) │ • Create / edit / suspend / delete users                   │
│              │ • Create custom roles with any permissions                 │
│              │ • Change existing role permissions                         │
│              │ • Build pipeline templates (multi-step workflows)          │
│              │ • Change app name, company name, primary color             │
│              │ • Rename any UI label (e.g. "SR" → "Ticket")              │
│              │ • Configure WhatsApp (QR or Meta API)                      │
│              │ • Configure Email (SMTP)                                   │
│              │ • Set notification triggers                                │
│              │ • View full audit log                                      │
│              │ • Export all SRs to CSV                                    │
│              │ • Wipe all SRs (danger zone)                               │
│              │ • View statistics for ALL users                            │
├──────────────┼────────────────────────────────────────────────────────────┤
│              │ • Create SRs and assign to technical users                 │
│   MANAGER    │ • View ALL service requests                                │
│              │ • Re-assign SRs to different users                         │
│              │ • Close completed SRs                                      │
│              │ • Monitor pipeline progress per SR                         │
│              │ • See technician availability when assigning               │
│              │ • View statistics for their team                           │
│              │ • Filter SRs by status                                     │
│              │ • Search SRs by title/description                          │
├──────────────┼────────────────────────────────────────────────────────────┤
│              │ • View SRs assigned to them or created by them             │
│  TECHNICAL   │ • Create self-assigned SRs                                 │
│              │ • Update SR status: Open → In Progress → Completed         │
│              │ • Advance pipeline steps (their role's steps)              │
│              │ • Skip pipeline steps with a mandatory written reason      │
│              │ • Add progress notes per step                              │
│              │ • Send help request email to admin/managers                │
│              │ • View their own statistics                                │
└──────────────┴────────────────────────────────────────────────────────────┘

  CUSTOM ROLES:
    Admin can create roles like "Supervisor", "L1 Support", "Client Rep"
    and assign any combination of the above permissions to them.
    Go to: Admin Dashboard → Roles tab → "+ New Role"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  10. ADMIN GOD PANEL — FULL GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When you log in as Admin you see 7 tabs in the left sidebar:

────────────────────────────────────
TAB 1: 👥 Users
────────────────────────────────────
  Shows all users with:
    • Name, Email, Role, WhatsApp number, Created date
    • KPI cards: Total / Admins / Managers / Technicals

  Actions per user:
    • Change role via dropdown → click "Save"
    • 🚫 button → Suspend / Reactivate the user

  "+ Create User" button → opens dialog:
    • Full name
    • Email
    • Password (min 6 characters)
    • WhatsApp number (for receiving notifications)
    • Role (any built-in or custom role)

  ⚠  Deleting a user: Currently suspend them. Full delete coming in a
     future update. You can delete from Firebase Console directly if needed.

────────────────────────────────────
TAB 2: 📋 All SRs
────────────────────────────────────
  Read-only overview of every service request in the system.
  Shows: Title, Type, Status, Priority, Pipeline, Assigned To, Created.
  Useful for oversight — use the Manager dashboard for actions.

────────────────────────────────────
TAB 3: 🔧 Pipelines
────────────────────────────────────
  Create multi-step approval workflows. See Section 13 for full details.

────────────────────────────────────
TAB 4: 🔑 Roles
────────────────────────────────────
  • View all built-in roles and their permissions
  • Edit permissions of built-in roles (admin can restrict managers, etc.)
  • Create custom roles with a permission checklist

  Permission categories:
    SR Management:    view SRs, create, update, assign, close, skip steps
    User Management:  create, edit, delete users, manage roles
    Reports & Data:   view own reports, view all reports, export, audit log
    System:           settings, notifications, branding, pipelines, danger zone

────────────────────────────────────
TAB 5: 📊 Statistics
────────────────────────────────────
  Full statistics dashboard. See Section 17 for full details.

────────────────────────────────────
TAB 6: ⚙️ Settings
────────────────────────────────────
  5 sub-tabs. See Sections 14–18 for detailed setup guides.

  🎨 Branding:     App name, company name, primary colour, label overrides
  📱 WhatsApp:     QR mode or Meta Cloud API, report schedule, template
  📧 Email:        Gmail SMTP credentials, email template
  🔔 Notifications: Per-event toggles, audit log on/off
  ☠ Danger Zone:  Export CSV, reset settings, wipe all SRs

────────────────────────────────────
TAB 7: 📜 Audit Log
────────────────────────────────────
  Every action in the system is logged here automatically:
    • Who did it (name, role)
    • What they did (SR created, user created, step skipped, etc.)
    • When (timestamp)
    • Target (SR ID, user UID, etc.)

  Sorted newest first. Enable/disable in Settings → Notifications.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  11. MANAGER DASHBOARD — FULL GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Left sidebar filters:
  📋 All SRs        — show everything
  🔵 Open           — not yet started
  🟡 In Progress    — being worked on
  🟢 Completed      — done by technical, awaiting close
  ⚫ Closed         — fully closed
  📊 Statistics     — switch to stats view

Top right:
  "+ New SR" → Create and assign a service request

SR Table shows:
  Title | Type | Priority | Status | Pipeline | Assigned To | Created | Actions

Actions per SR:
  📂 Open  → Full detail dialog (re-assign, view pipeline, close SR)
  ✅       → Quick close the SR

────────────────────────────────────
CREATING A SERVICE REQUEST (Manager)
────────────────────────────────────
  1. Click "+ New SR"
  2. Fill in Title (required)
  3. Fill in Description (required)
  4. Select a Pipeline Template (or "No Template" for freeform)
     → When a template is selected, the steps are shown as a preview
  5. Select who to Assign To
     → Each person shows their availability:
        🟢 Available  — 0 active SRs
        🟡 Moderate   — 1-2 active SRs
        🔴 Busy       — 3+ active SRs
  6. Select Priority: Low / Medium / High
  7. Click "Create SR"

The assigned technical user will see it within 3 seconds.

────────────────────────────────────
VIEWING SR DETAILS & PIPELINE
────────────────────────────────────
  Click "📂 Open" on any SR to see:
  • Status badge and priority badge
  • Full description
  • Pipeline steps with current position highlighted
    ✅ Done  ▶ Current  ○ Pending  ⏭ Skipped
  • Re-assign dropdown (with availability indicators)
  • "Close SR" button


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  12. TECHNICAL DASHBOARD — FULL GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Technical users ONLY see SRs:
  • Assigned to them by a manager, OR
  • Created by themselves (self-created)

Left sidebar filters:
  📋 My SRs      — all their SRs
  🔵 Open        — not started
  🟡 In Progress — working on it
  🟢 Completed   — done
  📊 My Stats    — their personal statistics

Top right buttons:
  📧 Request Help  → Sends email to all admins and managers
  + New SR         → Create a self-assigned SR

SR Table shows:
  Title | Type | Priority | Status | Pipeline | Updated | Actions

Actions:
  ✏ Update   → Open update dialog (change status + pipeline step)
  ▶          → Quick-start (Open → In Progress)
  ✅          → Quick-complete (In Progress → Completed)

────────────────────────────────────
CREATING A SELF-ASSIGNED SR (Technical)
────────────────────────────────────
  1. Click "+ New SR"
  2. Fill in Title
  3. Fill in Description
  4. Select Priority
  5. Click "Create SR"
  → SR is automatically assigned to yourself. No manager selection needed.
  → Managers can see and monitor it.

────────────────────────────────────
UPDATING AN SR WITH PIPELINE STEPS
────────────────────────────────────
  1. Click "✏ Update" on an SR
  2. If the SR has a pipeline template:
       → You see each step with its status
       → The current step is shown with ▶
       → If it's your role's step, you see action buttons
       → Click "✅ Complete: [Step Name]" to advance
       → Click "⏭ Skip Step" to skip (you must enter a reason)
  3. If no pipeline (freeform):
       → Select new status from dropdown
       → Add progress notes
       → Click "Save Update"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  13. PIPELINE / APPROVAL PROCESS — FULL GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pipelines let you define multi-step approval processes for different
types of service requests. Each template has ordered steps, and each
step has an "approver role" — the person who must complete it.

────────────────────────────────────
CREATING A PIPELINE TEMPLATE
────────────────────────────────────
  1. Login as Admin
  2. Go to: Admin Dashboard → 🔧 Pipelines tab
  3. Click "+ New Template"
  4. Enter a template name (e.g. "Enterprise Installation")
  5. Enter a description (optional)
  6. Click "+ Add Step" for each step

  For each step:
    • Step Name: e.g. "Welcome Letter Sent"
    • Description: optional details
    • Approver Role: which role must complete this step
        → technical / manager / admin (or any custom role)
    • Required: tick if this step cannot be skipped
    • Skippable: tick if users can skip it (with a reason)

  7. Click "💾 Save Template"

────────────────────────────────────
EXAMPLE TEMPLATES
────────────────────────────────────

  Template: "Enterprise Cloud Installation"
  ┌──────┬──────────────────────────────┬──────────────┬──────────┐
  │ Step │ Name                         │ Approver     │ Required │
  ├──────┼──────────────────────────────┼──────────────┼──────────┤
  │  1   │ Welcome Letter Sent          │ manager      │ Yes      │
  │  2   │ Site Survey Completed        │ technical    │ Yes      │
  │  3   │ Cloud Environment Setup      │ technical    │ Yes      │
  │  4   │ Client Walkthrough           │ manager      │ Yes      │
  │  5   │ Sign-off & Handover          │ manager      │ Yes      │
  └──────┴──────────────────────────────┴──────────────┴──────────┘

  Template: "Basic Installation"
  ┌──────┬──────────────────────────────┬──────────────┬──────────┐
  │ Step │ Name                         │ Approver     │ Required │
  ├──────┼──────────────────────────────┼──────────────┼──────────┤
  │  1   │ Site Survey                  │ technical    │ Yes      │
  │  2   │ Installation                 │ technical    │ Yes      │
  │  3   │ Testing                      │ technical    │ Yes      │
  │  4   │ Manager Sign-off             │ manager      │ Yes      │
  └──────┴──────────────────────────────┴──────────────┴──────────┘

  Template: "No Template" — Select this for simple freeform SRs that
  don't need a multi-step process. Status goes Open → In Progress → Completed
  without any step tracking.

────────────────────────────────────
HOW PIPELINE WORKS (FLOW)
────────────────────────────────────

  Manager creates SR → selects "Enterprise Cloud Installation" template
       ↓
  SR is created with pipeline state: Step 1 of 5 (Welcome Letter Sent)
  Manager dashboard shows: "Enterprise Cloud Installation (1/5)"
       ↓
  Manager completes Step 1 (Welcome Letter Sent — manager's step)
  → clicks "✅ Complete: Welcome Letter Sent"
       ↓
  Pipeline advances to Step 2 (Site Survey — technical's step)
  Technical user sees it in their dashboard
       ↓
  Technical completes Steps 2, 3 one by one
       ↓
  Pipeline moves to Steps 4, 5 (manager's steps)
       ↓
  When all steps done → SR automatically marked "Completed"
  Manager can then close it.

────────────────────────────────────
SKIPPING A STEP
────────────────────────────────────
  If a step is marked "Skippable":
    1. Click "✏ Update" on the SR
    2. Click "⏭ Skip Step"
    3. A dialog appears asking for a REASON (mandatory)
    4. Enter the reason and click OK
    → Step is marked as ⏭ Skipped with the reason stored
    → Audit log records who skipped it and why
    → Pipeline advances to the next step


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  14. WHATSAPP SETUP — QR MODE (Scan Your Own Number)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QR mode lets you use your own personal WhatsApp number to send messages.
You scan a QR code once per session (like WhatsApp Web on a browser).

────────────────────────────────────
ONE-TIME SETUP
────────────────────────────────────
  1. Install the WebEngine package (one-time):
       pip install PyQt6-WebEngine

  2. Login as Admin → ⚙️ Settings → 📱 WhatsApp tab

  3. Make sure "Mode" is set to:
       📱 QR Code (WhatsApp Web — scan once)

  4. The WhatsApp Web page loads inside the app.

  5. On your phone:
       WhatsApp → ⋮ Menu (3 dots) → Linked Devices → Link a Device

  6. Scan the QR code shown in the app.

  7. The status bar shows: ✅ WhatsApp connected

  8. Now fill in the recipient numbers for each user:
       Admin Dashboard → Users → find the user → add their WhatsApp number
       Format: +91XXXXXXXXXX (include country code)

  9. Set the Daily Report Time (e.g. 09:00) and template.

  10. Click "💾 Save All Settings"

  ⚠  NOTES:
     • You need to keep the app open (or minimised) for WhatsApp to work.
     • WhatsApp may disconnect after some hours — just re-scan the QR.
     • WhatsApp's terms of service don't officially allow automation.
       Use at your own risk for internal business use.
     • For production/commercial use, use Meta Cloud API (Section 15).

────────────────────────────────────
TESTING WHATSAPP QR
────────────────────────────────────
  In Settings → 📱 WhatsApp → click "📤 Send Test Message"
  Enter a phone number and test message → click Send.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  15. WHATSAPP SETUP — META CLOUD API MODE (Company Number)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Meta Cloud API uses one company WhatsApp number that sends TO each user's
personal number. Free tier: 1,000 conversations/month.

────────────────────────────────────
SETUP (10-15 minutes)
────────────────────────────────────
  1. Go to: https://developers.facebook.com/

  2. Create a developer account (or log in with Facebook).

  3. Go to "My Apps" → "Create App".

  4. Choose "Business" → Next.

  5. Enter an app name → Create App.

  6. In your app dashboard → click "WhatsApp" → "Set up".

  7. Follow the steps to add a WhatsApp Business phone number.
     (You can use a new number or add an existing one.)

  8. In WhatsApp → API Setup, you will see:
       • Phone number ID    → copy this
       • Temporary access token → copy this
         (For permanent token: Meta Business Settings → System Users)

  9. In SR Manager:
       Login as Admin → ⚙️ Settings → 📱 WhatsApp
       Change Mode to: ☁ Meta Cloud API (Business number)
       Paste Phone Number ID
       Paste Access Token
       Click "📤 Send Test (Meta)" to verify

  10. Each user must have their personal WhatsApp number in their profile:
        Admin Dashboard → Users → save role → number field

  11. Click "💾 Save All Settings"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  16. EMAIL / SMTP SETUP (Gmail)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Email is used for:
  • Technical users sending "Help Request" to managers
  • Any future email notification features

────────────────────────────────────
GMAIL APP PASSWORD SETUP
────────────────────────────────────
  Regular Gmail passwords don't work for SMTP. You need an "App Password".

  1. Go to your Google Account: https://myaccount.google.com/

  2. Click "Security" in the left menu.

  3. Under "How you sign in to Google" → click "2-Step Verification"
     (Enable it if not already on).

  4. Scroll down to "App passwords".

  5. Click "App passwords".

  6. Select app: "Mail"
     Select device: "Windows Computer"

  7. Click "Generate".

  8. Google shows a 16-character password (e.g. abcd efgh ijkl mnop).
     COPY this immediately — you won't see it again.

────────────────────────────────────
CONFIGURE IN THE APP
────────────────────────────────────
  1. Login as Admin → ⚙️ Settings → 📧 Email tab

  2. SMTP Email:    your Gmail address (e.g. company@gmail.com)

  3. SMTP Password: the 16-character App Password (no spaces)

  4. Email Template: customise the message wrapper (optional)
     Default: "{company_name}\n\n{body}"

  5. Click "📧 Send Test Email to Myself" to verify.

  6. Click "💾 Save All Settings"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  17. STATISTICS DASHBOARD — FULL GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All three roles have access to a statistics view. What they see differs:
  • Admin:     All users, all data
  • Manager:   Can filter by user or see all
  • Technical: Only their own SRs

────────────────────────────────────
KPI CARDS (top row)
────────────────────────────────────
  Total SRs       — total count (filtered by user if applicable)
  Open            — currently open
  In Progress     — currently being worked on
  Completed       — done, not yet closed
  Overdue         — open more than 3 days (shown in red)
  Avg Resolution  — average days from creation to completion

────────────────────────────────────
CHART TABS
────────────────────────────────────
  📈 SR Trend      — line chart of SRs created over the last 30 days
  🍩 Breakdown     — bar charts for status and priority distribution
  👥 Workload      — bar chart of active SRs per technician
                     + table with: Name, Availability, Active, Completed, Avg Days
  🔧 Pipelines     — average resolution time per pipeline template
  ⚠ Overdue       — table listing all overdue SRs with days open

────────────────────────────────────
FILTERING (Admin/Manager)
────────────────────────────────────
  Top right → "Filter:" dropdown → select "All Users" or a specific user.
  Charts and KPIs update automatically.

  "🔄 Refresh" button → manually reload data (auto-refreshes every 30s).

────────────────────────────────────
AVAILABILITY COLOUR SYSTEM
────────────────────────────────────
  🟢 Available    — 0 active SRs  (ready for new work)
  🟡 Moderate     — 1-2 active SRs (can take more)
  🔴 Busy         — 3+ active SRs (overloaded)

  This shows on:
    • Workload table in Statistics
    • Assign dropdown when creating or editing an SR


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  18. BRANDING & LABEL CUSTOMISATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Admin can change how the app looks and what things are called.
These changes apply to ALL users the next time they log in.

Go to: Admin Dashboard → ⚙️ Settings → 🎨 Branding

────────────────────────────────────
APP IDENTITY
────────────────────────────────────
  App Name:       Changes the window title and login screen heading.
                  e.g. "SR Manager" → "HelpDesk Pro"

  Company Name:   Shown on login screen, in WhatsApp/email messages.
                  e.g. "SR Manager" → "Acme Corp"

  Primary Color:  Click the colour button → pick any colour.
                  Changes sidebar, buttons, chart colours instantly.
                  The preview applies live before you even save.
                  e.g. blue (#3B82F6) → green (#10B981) or red (#EF4444)

────────────────────────────────────
LABEL OVERRIDES
────────────────────────────────────
  Change the name of any status or the main entity:

  'Service Request' →  e.g. "Work Order", "Ticket", "Job Card"
  'Open'            →  e.g. "New", "Pending", "Received"
  'In Progress'     →  e.g. "Active", "Working", "Under Review"
  'Completed'       →  e.g. "Done", "Resolved", "Finished"
  'Closed'          →  e.g. "Archived", "Signed Off"

  Leave blank to keep the default.
  These labels appear in all dashboards, tables, and status badges.

────────────────────────────────────
SAVING CHANGES
────────────────────────────────────
  Click "💾 Save All Settings"
  The colour applies immediately for the current session.
  All other changes apply on next login for all users.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  19. RUNNING THE APPLICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  OPTION A — Double-click (easiest):
    Double-click run_app.bat in the sr_manager_v2 folder.

  OPTION B — Command line:
    cd C:\path\to\sr_manager_v2
    python main.py

  OPTION C — From any folder:
    python C:\path\to\sr_manager_v2\main.py

  The app polls Firebase every 3 seconds.
  Changes made on one machine appear on all other machines within 3 seconds.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  20. BUILDING A STANDALONE EXE (No Python Required)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Once you build the EXE, you can copy it to any Windows machine and run it
without installing Python or any packages.

  1. Make sure firebase_client.py has YOUR Firebase keys (from Step 4).

  2. Double-click build_exe.bat
     OR run in Command Prompt:
       cd C:\path\to\sr_manager_v2
       build_exe.bat

  3. Wait 2-5 minutes. PyInstaller bundles everything.

  4. Find the EXE at:
       sr_manager_v2\dist\SR_Manager_v2.exe

  5. Copy SR_Manager_v2.exe to any Windows machine and run it.

  ⚠  NOTES:
     • Your Firebase credentials are baked into the EXE.
       Do not share it with people outside your organisation.
     • WhatsApp QR mode requires PyQt6-WebEngine to be installed BEFORE
       you run build_exe.bat.
     • The first launch may take 5-10 seconds (normal for PyInstaller apps).
     • Windows Defender may flag it — click "More info" → "Run anyway".
       This is normal for unsigned Python EXEs.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  21. FIRESTORE COLLECTIONS REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

These are all the Firestore collections the app reads from and writes to:

  ┌──────────────────────┬─────────────────────────────────────────────────┐
  │ Collection           │ Purpose                                         │
  ├──────────────────────┼─────────────────────────────────────────────────┤
  │ users                │ All user profiles (name, email, role, WA no.)   │
  │ service_requests     │ All SRs with status, pipeline_state, notes      │
  │ pipeline_templates   │ Admin-defined workflow templates                │
  │ roles                │ Custom roles with permission lists              │
  │ role_overrides       │ Permission overrides for built-in roles         │
  │ audit_log            │ Every action logged (who, what, when, target)   │
  │ settings/global_config│ App name, colors, WA/email config, labels     │
  └──────────────────────┴─────────────────────────────────────────────────┘

  You can view and edit all of this directly in:
  Firebase Console → Firestore Database → select the collection.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  22. TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBLEM: "ModuleNotFoundError: No module named 'PyQt6'"
SOLUTION: Run:  pip install PyQt6
──────────────────────────────────────────────────────────────────────────────

PROBLEM: "ModuleNotFoundError: No module named 'PyQt6.QtWebEngineWidgets'"
SOLUTION: Run:  pip install PyQt6-WebEngine
          This is only needed for WhatsApp QR mode.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: Login fails with "Invalid email or password"
SOLUTION: Check Firebase Console → Authentication → your user exists.
          Make sure the user document also exists in Firestore → users.
          Both must exist (Auth user + Firestore document).
──────────────────────────────────────────────────────────────────────────────

PROBLEM: "Your account exists but is not in the database"
SOLUTION: The Firebase Auth user exists but has no Firestore document.
          Go to Firestore → users collection → add a document.
          Document ID must equal the user's Firebase UID.
          Fields needed: uid, email, name, role, active (true), created_at
──────────────────────────────────────────────────────────────────────────────

PROBLEM: "⚠ Sync Error" shown in the sidebar
SOLUTION: Check your internet connection.
          If internet is fine, check Firebase Console → Firestore is active.
          The app will recover automatically when connection is restored.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: WhatsApp QR code not loading
SOLUTION: Make sure PyQt6-WebEngine is installed:
            pip install PyQt6-WebEngine
          Click "🔄 Refresh" in the WhatsApp panel.
          Check your internet connection.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: Email sending fails "SMTP authentication failed"
SOLUTION: You need an App Password, not your regular Gmail password.
          See Section 16 for how to create one.
          Make sure 2-Step Verification is enabled on your Google account.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: App crashes on startup
SOLUTION: Run from command line to see the error:
            python main.py
          Most common cause: wrong Firebase keys in firebase_client.py
──────────────────────────────────────────────────────────────────────────────

PROBLEM: "INVALID_API_KEY" error
SOLUTION: Open firebase_client.py and check:
            FIREBASE_API_KEY    = "your key here"
            FIREBASE_PROJECT_ID = "your project id here"
          Make sure there are no spaces or extra quotes.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: EXE shows a Windows Defender warning
SOLUTION: Click "More info" → "Run anyway"
          This is normal for unsigned Python applications.
          The app is not malware — it is just not code-signed.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: Statistics charts are empty
SOLUTION: Charts require at least one SR to exist.
          Create a test SR from the Manager dashboard and check again.
──────────────────────────────────────────────────────────────────────────────

PROBLEM: Pipeline steps not advancing
SOLUTION: Only the user whose ROLE matches the step's "Approver Role" can
          advance that step. Check the step's approver role in the template
          (Admin → Pipelines → view the template).
          Admins can always advance any step.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  23. FREQUENTLY ASKED QUESTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: How many users can use the app at the same time?
A: No hard limit. Firebase Spark (free) plan supports up to 100 concurrent
   connections. Firebase Blaze (pay-as-you-go) supports unlimited.
   For a team of under 50 people the free plan is more than enough.

──────────────────────────────────────────────────────────────────────────────
Q: Is the data secure?
A: Yes. All data goes through Firebase over HTTPS (TLS). Only authenticated
   users can read or write data (enforced by Firestore security rules).
   No data is stored locally on the machine.

──────────────────────────────────────────────────────────────────────────────
Q: Can I run it on multiple machines at the same time?
A: Yes. This is the main use case. All machines sync every 3 seconds.
   Changes on one machine appear on all others within 3 seconds.

──────────────────────────────────────────────────────────────────────────────
Q: What happens if the internet goes down?
A: The app shows "⚠ Sync Error" in the sidebar. Login will not work
   without internet. When connection is restored, polling resumes automatically.

──────────────────────────────────────────────────────────────────────────────
Q: Can I change a user's role without them logging out?
A: The role change saves to Firestore immediately. It takes effect the
   next time that user logs in or restarts the app.

──────────────────────────────────────────────────────────────────────────────
Q: Can I delete a service request?
A: Not from the app UI (by design — for audit purposes). You can:
   • Close the SR (preferred)
   • Use "Wipe All SRs" in Admin → Settings → Danger Zone (deletes all)
   • Delete individual SRs directly from Firebase Console → Firestore

──────────────────────────────────────────────────────────────────────────────
Q: How do I add a user's WhatsApp number?
A: Admin Dashboard → Users tab → find the user → the WhatsApp field is
   shown. Change role to same value → Save (this also saves the number).
   OR: Edit the user document directly in Firebase Console → Firestore
   → users → find the document → add field: whatsapp_number (string).

──────────────────────────────────────────────────────────────────────────────
Q: Does the daily WhatsApp report send automatically?
A: Yes, as long as the app is running on at least one machine.
   The background scheduler checks every 60 seconds.
   At the configured report_time (e.g. 09:00) it sends the report once.
   Set the time in Admin → Settings → 📱 WhatsApp → "Daily Report Time".

──────────────────────────────────────────────────────────────────────────────
Q: What is the difference between "Completed" and "Closed"?
A: Completed: Technical user has finished the work.
   Closed:    Manager has reviewed and officially closed the SR.
   This two-step process ensures manager sign-off before archiving.

──────────────────────────────────────────────────────────────────────────────
Q: Can a Technical user see SRs assigned to other technicians?
A: No. Technical users only see SRs where they are the assigned user
   or the creator. Managers and Admins see all SRs.

──────────────────────────────────────────────────────────────────────────────
Q: How do I reset a forgotten admin password?
A: Go to Firebase Console → Authentication → find the user →
   click the 3-dot menu → "Reset password". Firebase emails a reset link.

──────────────────────────────────────────────────────────────────────────────
Q: Can I rename "Service Request" to "Work Order" everywhere?
A: Yes. Admin → Settings → 🎨 Branding → 'Service Request' → type "Work Order"
   → Save. The label changes throughout the app.

──────────────────────────────────────────────────────────────────────────────


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUICK REFERENCE — FIRST TIME SETUP CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  □  Step 1: Create Firebase project at console.firebase.google.com
  □  Step 2: Enable Email/Password authentication
  □  Step 3: Create Firestore database (production mode)
  □  Step 4: Set Firestore security rules (allow read, write if auth != null)
  □  Step 5: Get your API Key and Project ID from Project Settings
  □  Step 6: Open firebase_client.py and paste your API Key + Project ID
  □  Step 7: pip install -r requirements.txt
  □  Step 8: (Optional) pip install PyQt6-WebEngine (for WhatsApp QR)
  □  Step 9: Create admin user in Firebase Console → Authentication
  □  Step 10: Create admin user document in Firestore → users collection
  □  Step 11: Run the app and log in as admin
  □  Step 12: Go to Settings and configure branding, WhatsApp, email
  □  Step 13: Create pipeline templates if needed
  □  Step 14: Create manager and technical user accounts from the app
  □  Step 15: Share the app (or EXE) with your team


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SR Manager v2 — Built with PyQt6 + Firebase REST API
  Designed for production use. Always ready for upgrades.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
