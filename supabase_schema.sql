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

-- Current balances for each bank, wallet, or cash account.
create table if not exists public.accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    name text not null check (char_length(trim(name)) between 1 and 100),
    balance bigint not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, name)
);

create index if not exists accounts_user_id_idx
    on public.accounts using btree (user_id);

alter table public.accounts enable row level security;

revoke all on table public.accounts from anon, authenticated;
grant select, insert, update, delete on table public.accounts to authenticated;

drop policy if exists "Users can read their own accounts" on public.accounts;
create policy "Users can read their own accounts"
    on public.accounts
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own accounts" on public.accounts;
create policy "Users can add their own accounts"
    on public.accounts
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own accounts" on public.accounts;
create policy "Users can update their own accounts"
    on public.accounts
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own accounts" on public.accounts;
create policy "Users can delete their own accounts"
    on public.accounts
    for delete
    to authenticated
    using ((select auth.uid()) = user_id);

-- Audit trail for money entering, leaving, or moving between accounts.
create table if not exists public.account_movements (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    account_id uuid not null references public.accounts (id) on delete cascade,
    expense_id uuid references public.expenses (id) on delete set null,
    transfer_id uuid,
    movement_type text not null check (
        movement_type in (
            'initial',
            'deposit',
            'adjustment',
            'transfer_out',
            'transfer_in',
            'expense',
            'expense_refund'
        )
    ),
    amount bigint not null check (amount <> 0),
    note text not null default '' check (char_length(note) <= 500),
    created_at timestamptz not null default now()
);

create index if not exists account_movements_user_created_idx
    on public.account_movements using btree (user_id, created_at desc);

create index if not exists account_movements_account_idx
    on public.account_movements using btree (account_id, created_at desc);

alter table public.account_movements enable row level security;

revoke all on table public.account_movements from anon, authenticated;
grant select, insert on table public.account_movements to authenticated;

drop policy if exists "Users can read their own account movements"
    on public.account_movements;
create policy "Users can read their own account movements"
    on public.account_movements
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own account movements"
    on public.account_movements;
create policy "Users can add their own account movements"
    on public.account_movements
    for insert
    to authenticated
    with check (
        (select auth.uid()) = user_id
        and exists (
            select 1
            from public.accounts
            where accounts.id = account_movements.account_id
              and accounts.user_id = (select auth.uid())
        )
    );

-- Create an account and record its opening balance.
create or replace function public.wonwise_create_account(
    p_name text,
    p_opening_balance bigint
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_account_id uuid;
    v_name text := trim(p_name);
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;
    if char_length(v_name) < 1 then
        raise exception 'Account name is required.';
    end if;
    if p_opening_balance < 0 then
        raise exception 'Opening balance cannot be negative.';
    end if;

    insert into public.accounts (user_id, name, balance)
    values (v_user_id, v_name, p_opening_balance)
    returning id into v_account_id;

    if p_opening_balance > 0 then
        insert into public.account_movements (
            user_id, account_id, movement_type, amount, note
        ) values (
            v_user_id, v_account_id, 'initial', p_opening_balance, 'Opening balance'
        );
    end if;

    return v_account_id;
end;
$$;

-- Add incoming money such as salary, allowance, or a cash top-up.
create or replace function public.wonwise_add_money(
    p_account_id uuid,
    p_amount bigint,
    p_note text
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;
    if p_amount <= 0 then
        raise exception 'Amount must be greater than zero.';
    end if;

    update public.accounts
    set balance = balance + p_amount,
        updated_at = now()
    where id = p_account_id
      and user_id = v_user_id;

    if not found then
        raise exception 'Account not found.';
    end if;

    insert into public.account_movements (
        user_id, account_id, movement_type, amount, note
    ) values (
        v_user_id, p_account_id, 'deposit', p_amount, coalesce(trim(p_note), '')
    );
end;
$$;

-- Correct an account when the real bank balance differs from WonWise.
create or replace function public.wonwise_set_balance(
    p_account_id uuid,
    p_new_balance bigint,
    p_note text
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_old_balance bigint;
    v_difference bigint;
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;
    if p_new_balance < 0 then
        raise exception 'Balance cannot be negative.';
    end if;

    select balance
    into v_old_balance
    from public.accounts
    where id = p_account_id
      and user_id = v_user_id
    for update;

    if not found then
        raise exception 'Account not found.';
    end if;

    v_difference := p_new_balance - v_old_balance;
    update public.accounts
    set balance = p_new_balance,
        updated_at = now()
    where id = p_account_id;

    if v_difference <> 0 then
        insert into public.account_movements (
            user_id, account_id, movement_type, amount, note
        ) values (
            v_user_id,
            p_account_id,
            'adjustment',
            v_difference,
            coalesce(nullif(trim(p_note), ''), 'Balance correction')
        );
    end if;
end;
$$;

-- Move money without counting it as spending.
create or replace function public.wonwise_transfer_funds(
    p_from_account_id uuid,
    p_to_account_id uuid,
    p_amount bigint,
    p_note text
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_source_balance bigint;
    v_transfer_id uuid := gen_random_uuid();
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;
    if p_from_account_id = p_to_account_id then
        raise exception 'Choose two different accounts.';
    end if;
    if p_amount <= 0 then
        raise exception 'Amount must be greater than zero.';
    end if;

    perform 1
    from public.accounts
    where id in (p_from_account_id, p_to_account_id)
      and user_id = v_user_id
    order by id
    for update;

    if (
        select count(*)
        from public.accounts
        where id in (p_from_account_id, p_to_account_id)
          and user_id = v_user_id
    ) <> 2 then
        raise exception 'One or both accounts were not found.';
    end if;

    select balance
    into v_source_balance
    from public.accounts
    where id = p_from_account_id;

    if v_source_balance < p_amount then
        raise exception 'Insufficient balance in the source account.';
    end if;

    update public.accounts
    set balance = balance - p_amount,
        updated_at = now()
    where id = p_from_account_id;

    update public.accounts
    set balance = balance + p_amount,
        updated_at = now()
    where id = p_to_account_id;

    insert into public.account_movements (
        user_id, account_id, transfer_id, movement_type, amount, note
    ) values
        (
            v_user_id,
            p_from_account_id,
            v_transfer_id,
            'transfer_out',
            -p_amount,
            coalesce(trim(p_note), '')
        ),
        (
            v_user_id,
            p_to_account_id,
            v_transfer_id,
            'transfer_in',
            p_amount,
            coalesce(trim(p_note), '')
        );
end;
$$;

-- Save a new expense and debit its tracked account in one transaction.
create or replace function public.wonwise_add_expense(
    p_account_id uuid,
    p_expense_date date,
    p_category text,
    p_amount bigint,
    p_note text
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_account_name text;
    v_expense_id uuid;
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;
    if p_amount <= 0 then
        raise exception 'Amount must be greater than zero.';
    end if;

    select name
    into v_account_name
    from public.accounts
    where id = p_account_id
      and user_id = v_user_id
    for update;

    if not found then
        raise exception 'Account not found.';
    end if;

    insert into public.expenses (
        user_id, expense_date, category, bank, amount, note
    ) values (
        v_user_id,
        p_expense_date,
        trim(p_category),
        v_account_name,
        p_amount,
        coalesce(trim(p_note), '')
    )
    returning id into v_expense_id;

    update public.accounts
    set balance = balance - p_amount,
        updated_at = now()
    where id = p_account_id;

    insert into public.account_movements (
        user_id, account_id, expense_id, movement_type, amount, note
    ) values (
        v_user_id,
        p_account_id,
        v_expense_id,
        'expense',
        -p_amount,
        coalesce(trim(p_note), '')
    );

    return v_expense_id;
end;
$$;

-- Deleting a newly tracked expense returns its money to the same account.
-- Imported historical expenses have no balance movement and are simply deleted.
create or replace function public.wonwise_delete_expense(
    p_expense_id uuid
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_account_id uuid;
    v_refund bigint;
begin
    if v_user_id is null then
        raise exception 'You must be signed in.';
    end if;

    if not exists (
        select 1
        from public.expenses
        where id = p_expense_id
          and user_id = v_user_id
    ) then
        raise exception 'Expense not found.';
    end if;

    select account_id, -amount
    into v_account_id, v_refund
    from public.account_movements
    where expense_id = p_expense_id
      and user_id = v_user_id
      and movement_type = 'expense'
      and amount < 0
    order by created_at
    limit 1
    for update;

    if found then
        update public.accounts
        set balance = balance + v_refund,
            updated_at = now()
        where id = v_account_id
          and user_id = v_user_id;

        insert into public.account_movements (
            user_id, account_id, movement_type, amount, note
        ) values (
            v_user_id,
            v_account_id,
            'expense_refund',
            v_refund,
            'Deleted expense refund'
        );
    end if;

    delete from public.expenses
    where id = p_expense_id
      and user_id = v_user_id;
end;
$$;

revoke all on function public.wonwise_create_account(text, bigint) from public;
revoke all on function public.wonwise_add_money(uuid, bigint, text) from public;
revoke all on function public.wonwise_set_balance(uuid, bigint, text) from public;
revoke all on function public.wonwise_transfer_funds(uuid, uuid, bigint, text) from public;
revoke all on function public.wonwise_add_expense(uuid, date, text, bigint, text) from public;
revoke all on function public.wonwise_delete_expense(uuid) from public;

grant execute on function public.wonwise_create_account(text, bigint) to authenticated;
grant execute on function public.wonwise_add_money(uuid, bigint, text) to authenticated;
grant execute on function public.wonwise_set_balance(uuid, bigint, text) to authenticated;
grant execute on function public.wonwise_transfer_funds(uuid, uuid, bigint, text) to authenticated;
grant execute on function public.wonwise_add_expense(uuid, date, text, bigint, text) to authenticated;
grant execute on function public.wonwise_delete_expense(uuid) to authenticated;
