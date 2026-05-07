# SR Manager — Firebase → Supabase Migration Guide

## Why Supabase?

| Feature | Firebase / Firestore | Supabase |
|---|---|---|
| Free tier | 1 GB / 50k reads per day | 500 MB DB, unlimited API calls |
| Auth | ✅ | ✅ |
| REST API | ✅ | ✅ (PostgREST — cleaner, no SDK needed) |
| Open source | ❌ | ✅ |
| Self-hostable | ❌ | ✅ |
| Offline error-prone | Yes (random unknown errors) | Stable PostgreSQL backend |

---

## Setup (5 minutes)

### 1. Create a free Supabase project
1. Go to https://supabase.com → Sign Up (free)
2. Click **New Project**, pick a name and a strong DB password
3. Wait ~2 minutes for provisioning

### 2. Get your credentials
In your project → **Settings → API**:
- Copy **Project URL** (looks like `https://abcdef.supabase.co`)
- Copy **anon / public** key

### 3. Paste credentials into `supabase_client.py`
Open `supabase_client.py` and replace lines 32–33:
```python
SUPABASE_URL      = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
```

### 4. Create the database tables
1. In Supabase dashboard → **SQL Editor → New Query**
2. Paste the entire contents of `supabase_schema.sql`
3. Click **Run**

### 5. Disable email confirmation (for desktop app use)
In Supabase → **Authentication → Settings → Email**:
- Turn OFF **Confirm email** toggle
- This lets `create_user()` work instantly like Firebase did

### 6. Create your first admin user
In Supabase → **Authentication → Users → Invite user**  
(Or run the app and use `create_user()` from admin panel)

Then in SQL Editor, add their user record:
```sql
insert into users (uid, email, name, role)
values ('PASTE_AUTH_UID_HERE', 'admin@yourcompany.com', 'Admin', 'admin');
```

---

## What changed in the code

| File | Change |
|---|---|
| `firebase_client.py` | **Deleted** |
| `supabase_client.py` | **New** — drop-in replacement, same API |
| `supabase_schema.sql` | **New** — run once to create tables |
| All `*.py` imports | `from firebase_client import firebase` → `from supabase_client import firebase` |
| `requirements.txt` | Removed firebase note, updated comment |

The error class names `FirebaseAuthError` and `FirebaseNetworkError` are intentionally kept in `supabase_client.py` so no `except` blocks need changing.

---

## Data types note

Firestore stored complex nested objects in its own format. Supabase uses real PostgreSQL columns. Fields like `pipeline_state` and `steps` (arrays of dicts) are stored as **JSONB**, which is actually more reliable and queryable.

---

## Troubleshooting

**"Invalid email or password"** — Make sure email confirmation is disabled in Supabase Auth settings.

**"Create failed: 42501"** — Row Level Security is blocking the insert. Make sure you ran the full `supabase_schema.sql` which creates the RLS policies.

**"relation does not exist"** — The SQL schema wasn't run. Go to SQL Editor and run `supabase_schema.sql`.
