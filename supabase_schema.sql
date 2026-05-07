-- supabase_schema.sql
-- Run this inside your Supabase project: SQL Editor → New Query → Paste → Run
-- This creates all tables that replace the Firestore collections used by SR Manager.

-- ── Enable UUID extension ──────────────────────────────────────────────────────
create extension if not exists "uuid-ossp";

-- ── USERS ─────────────────────────────────────────────────────────────────────
create table if not exists users (
    id          text primary key default gen_random_uuid()::text,
    uid         text unique,             -- Supabase Auth UID
    email       text unique not null,
    name        text not null default '',
    role        text not null default 'technical',
    whatsapp    text default '',
    phone       text default '',
    active      boolean default true,
    created_at  text default (now() at time zone 'utc')::text,
    updated_at  text default (now() at time zone 'utc')::text
);

-- ── ROLES ─────────────────────────────────────────────────────────────────────
create table if not exists roles (
    id           text primary key default gen_random_uuid()::text,
    name         text unique not null,
    label        text default '',
    permissions  jsonb default '[]'::jsonb,
    created_at   text default (now() at time zone 'utc')::text,
    updated_at   text default (now() at time zone 'utc')::text
);

-- ── SERVICE REQUESTS ──────────────────────────────────────────────────────────
create table if not exists service_requests (
    id              text primary key default gen_random_uuid()::text,
    title           text not null default '',
    description     text default '',
    status          text default 'Open',
    priority        text default 'Normal',
    category        text default '',
    location        text default '',
    created_by      text default '',        -- UID of creator
    assigned_to     text default '',        -- UID of assigned user
    assigned_name   text default '',
    client_name     text default '',
    client_phone    text default '',
    pipeline_state  jsonb default null,
    notes           text default '',
    created_at      text default (now() at time zone 'utc')::text,
    updated_at      text default (now() at time zone 'utc')::text,
    closed_at       text default ''
);

-- ── PIPELINE TEMPLATES ────────────────────────────────────────────────────────
create table if not exists pipeline_templates (
    id           text primary key default gen_random_uuid()::text,
    name         text not null default '',
    description  text default '',
    steps        jsonb default '[]'::jsonb,
    created_by   text default '',
    created_at   text default (now() at time zone 'utc')::text,
    updated_at   text default (now() at time zone 'utc')::text
);

-- ── AUDIT LOG ─────────────────────────────────────────────────────────────────
create table if not exists audit_log (
    id           text primary key default gen_random_uuid()::text,
    actor_uid    text default '',
    actor_name   text default '',
    actor_role   text default '',
    action       text not null,
    details      text default '',
    target_id    text default '',
    timestamp    text default (now() at time zone 'utc')::text
);

-- ── SETTINGS ──────────────────────────────────────────────────────────────────
-- One row per setting document (matches Firestore: settings/global_config)
create table if not exists settings (
    id             text primary key,       -- e.g. "global_config"
    app_name       text default 'SR Manager',
    company_name   text default 'SR Manager',
    primary_color  text default '#3B82F6',
    label_sr       text default 'Service Request',
    label_open     text default 'Open',
    label_in_progress text default 'In Progress',
    label_completed text default 'Completed',
    label_closed   text default 'Closed',
    whatsapp_mode  text default 'qr',
    whatsapp_number text default '',
    meta_phone_id  text default '',
    meta_access_token text default '',
    whatsapp_template text default '{company_name} Daily SR Report\n{report}',
    report_time    text default '09:00',
    notify_sr_created  text default 'true',
    notify_sr_assigned text default 'true',
    notify_step_done   text default 'true',
    notify_sr_closed   text default 'true',
    notify_daily_report text default 'true',
    smtp_email     text default '',
    smtp_password  text default '',
    email_template text default '{company_name}\n\n{body}',
    audit_enabled  text default 'true',
    updated_at     text default (now() at time zone 'utc')::text
);

-- Insert default global_config row so the app can read it on first boot
insert into settings (id) values ('global_config')
on conflict (id) do nothing;

-- ── ROW LEVEL SECURITY ────────────────────────────────────────────────────────
-- Enable RLS on all tables (Supabase best practice)
alter table users              enable row level security;
alter table roles              enable row level security;
alter table service_requests   enable row level security;
alter table pipeline_templates enable row level security;
alter table audit_log          enable row level security;
alter table settings           enable row level security;

-- Allow all operations for authenticated users (your app handles role auth itself)
-- You can tighten these later with per-role policies.
create policy "authenticated_all" on users              for all using (auth.role() = 'authenticated');
create policy "authenticated_all" on roles              for all using (auth.role() = 'authenticated');
create policy "authenticated_all" on service_requests   for all using (auth.role() = 'authenticated');
create policy "authenticated_all" on pipeline_templates for all using (auth.role() = 'authenticated');
create policy "authenticated_all" on audit_log          for all using (auth.role() = 'authenticated');
create policy "authenticated_all" on settings           for all using (auth.role() = 'authenticated');
