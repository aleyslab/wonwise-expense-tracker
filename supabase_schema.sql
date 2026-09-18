-- WonWise database schema
-- Run this entire file once in the Supabase SQL Editor.

create table if not exists public.expenses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    expense_date date not null default current_date,
    category text not null check (char_length(category) between 1 and 60),
    bank text not null check (char_length(bank) between 1 and 100),
    amount bigint not null check (amount > 0),
    note text not null default '' check (char_length(note) <= 500),
    created_at timestamptz not null default now()
);

create index if not exists expenses_user_id_idx
    on public.expenses using btree (user_id);

create index if not exists expenses_user_date_idx
    on public.expenses using btree (user_id, expense_date desc);

alter table public.expenses enable row level security;

revoke all on table public.expenses from anon, authenticated;
grant select, insert, update, delete on table public.expenses to authenticated;

drop policy if exists "Users can read their own expenses" on public.expenses;
create policy "Users can read their own expenses"
    on public.expenses
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own expenses" on public.expenses;
create policy "Users can add their own expenses"
    on public.expenses
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own expenses" on public.expenses;
create policy "Users can update their own expenses"
    on public.expenses
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own expenses" on public.expenses;
create policy "Users can delete their own expenses"
    on public.expenses
    for delete
    to authenticated
    using ((select auth.uid()) = user_id);
