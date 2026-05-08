-- SR Manager Enterprise 2026 — Supabase Schema
-- Run this entire file in your Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- No project URL or key is hardcoded; configure per installation.

-- ═══════════════════════════════════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════════════════════════════════
create extension if not exists "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════
-- TABLES
-- ═══════════════════════════════════════════════════════════════

-- Users
create table if not exists public.users (
    id                  text primary key,
    email               text unique not null,
    name                text,
    role                text not null default 'technical',
    whatsapp_number     text,
    active              boolean not null default true,
    is_master_admin     boolean not null default false,
    azure_oid           text,
    auth_provider       text default 'local',
    company_id          text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz
);

-- Roles (custom role definitions)
create table if not exists public.roles (
    id          text primary key,
    name        text not null,
    description text,
    permissions jsonb not null default '[]',
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- SR Entries (Service Requests)
create table if not exists public.sr_entries (
    id              text primary key,
    sr_number       text,
    title           text not null,
    description     text,
    sr_type         text not null default 'Service',
    status          text not null default 'open',
    priority        text not null default 'medium',
    customer_name   text,
    customer_phone  text,
    customer_email  text,
    customer_address text,
    assigned_to     text references public.users(id),
    created_by      text references public.users(id),
    pipeline_state  jsonb,
    comments        jsonb not null default '[]',
    attachments     jsonb not null default '[]',
    company_id      text,
    tags            jsonb not null default '[]',
    closed_at       timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Tasks
create table if not exists public.tasks (
    id           text primary key,
    title        text not null,
    description  text,
    sr_id        text references public.sr_entries(id),
    assigned_to  text references public.users(id),
    created_by   text references public.users(id),
    status       text not null default 'pending',
    priority     text not null default 'medium',
    due_date     timestamptz,
    completed_at timestamptz,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz
);

-- Pipeline Templates
create table if not exists public.pipelines (
    id          text primary key,
    name        text not null,
    description text,
    steps       jsonb not null default '[]',
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- Reports
create table if not exists public.reports (
    id          text primary key,
    title       text not null,
    type        text,
    data        jsonb not null default '{}',
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- Activity / Audit Logs
create table if not exists public.activity_logs (
    id          text primary key,
    action      text not null,
    details     text,
    target_id   text,
    actor_uid   text,
    actor_name  text,
    actor_role  text,
    timestamp   timestamptz not null default now()
);

-- Notifications
create table if not exists public.notifications (
    id          text primary key default gen_random_uuid()::text,
    title       text not null,
    message     text,
    level       text not null default 'info',
    user_id     text references public.users(id),
    read        boolean not null default false,
    created_at  timestamptz not null default now()
);

-- Attachments
create table if not exists public.attachments (
    id          text primary key,
    sr_id       text references public.sr_entries(id),
    filename    text not null,
    local_path   text,
    cloud_url    text,
    storage_path text,
    file_size    bigint,
    sha256       text,
    mime_type    text,
    uploaded_by  text references public.users(id),
    upload_error text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz
);

-- Analytics snapshots
create table if not exists public.analytics (
    id          text primary key default gen_random_uuid()::text,
    snapshot_at timestamptz not null default now(),
    period      text,
    data        jsonb not null default '{}'
);

-- Companies (multi-company support)
create table if not exists public.companies (
    id          text primary key default gen_random_uuid()::text,
    name        text not null,
    logo_url    text,
    settings    jsonb not null default '{}',
    created_at  timestamptz not null default now()
);

-- Mail templates
create table if not exists public.mail_templates (
    id          text primary key,
    name        text not null,
    subject     text,
    body        text,
    variables   jsonb not null default '[]',
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- WhatsApp templates
create table if not exists public.whatsapp_templates (
    id          text primary key,
    name        text not null,
    body        text not null,
    variables   jsonb not null default '[]',
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- Automation rules
create table if not exists public.automation_rules (
    id          text primary key,
    name        text not null,
    trigger     jsonb not null,
    conditions  jsonb not null default '[]',
    actions     jsonb not null default '[]',
    enabled     boolean not null default true,
    created_by  text references public.users(id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz
);

-- Settings (global config mirror)
create table if not exists public.settings (
    id          text primary key,
    data        jsonb not null default '{}'
);

-- ═══════════════════════════════════════════════════════════════
-- INDEXES (for query performance)
-- ═══════════════════════════════════════════════════════════════
create index if not exists idx_sr_entries_status        on public.sr_entries(status);
create index if not exists idx_sr_entries_assigned_to   on public.sr_entries(assigned_to);
create index if not exists idx_sr_entries_created_by    on public.sr_entries(created_by);
create index if not exists idx_sr_entries_updated_at    on public.sr_entries(updated_at desc);
create index if not exists idx_sr_entries_sr_type       on public.sr_entries(sr_type);
create index if not exists idx_tasks_assigned_to        on public.tasks(assigned_to);
create index if not exists idx_tasks_sr_id              on public.tasks(sr_id);
create index if not exists idx_activity_logs_timestamp  on public.activity_logs(timestamp desc);
create index if not exists idx_activity_logs_actor_uid  on public.activity_logs(actor_uid);
create index if not exists idx_notifications_user_id    on public.notifications(user_id);
create index if not exists idx_attachments_sr_id        on public.attachments(sr_id);
create index if not exists idx_attachments_updated_at   on public.attachments(updated_at desc);
create index if not exists idx_users_email              on public.users(email);

-- ═══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- Enable RLS on all tables — deny by default, grant via policies
-- ═══════════════════════════════════════════════════════════════
alter table public.users           enable row level security;
alter table public.roles           enable row level security;
alter table public.sr_entries      enable row level security;
alter table public.tasks           enable row level security;
alter table public.pipelines       enable row level security;
alter table public.reports         enable row level security;
alter table public.activity_logs   enable row level security;
alter table public.notifications   enable row level security;
alter table public.attachments     enable row level security;
alter table public.analytics       enable row level security;
alter table public.mail_templates  enable row level security;
alter table public.whatsapp_templates enable row level security;
alter table public.automation_rules   enable row level security;
alter table public.settings        enable row level security;

-- The desktop app is local-first; Supabase is only a lightweight mirror.
-- Prefer a least-privilege key and policies appropriate for your deployment.
-- The permissive service-role policy below is for private small-team installs only.

-- Service role policy (applied to all tables)
do $$
declare
    t text;
begin
    foreach t in array array[
        'users','roles','sr_entries','tasks','pipelines',
        'reports','activity_logs','notifications','attachments',
        'analytics','mail_templates','whatsapp_templates',
        'automation_rules','settings'
    ]
    loop
        execute format(
            'create policy if not exists "service_role_all_%s"
             on public.%I for all
             to service_role using (true) with check (true)',
            t, t
        );
    end loop;
end $$;

-- ═══════════════════════════════════════════════════════════════
-- HELPER FUNCTION: updated_at auto-update trigger
-- ═══════════════════════════════════════════════════════════════
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- Apply trigger to tables that have updated_at
do $$
declare
    t text;
begin
    foreach t in array array[
        'users','roles','sr_entries','tasks','pipelines',
        'reports','attachments','mail_templates','whatsapp_templates','automation_rules'
    ]
    loop
        execute format(
            'drop trigger if exists trg_set_updated_at on public.%I;
             create trigger trg_set_updated_at
             before update on public.%I
             for each row execute function public.set_updated_at()',
            t, t, t
        );
    end loop;
end $$;

-- Done. Run this script once in Supabase SQL Editor.
