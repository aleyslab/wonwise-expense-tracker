import calendar
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from supabase import Client, create_client


APP_TITLE = "WonWise Expense Tracker"

CATEGORIES = [
    "Food",
    "Transportation",
    "Shopping",
    "Housing",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Travel",
    "Other",
]

BANKS = [
    "Kakao Pay",
    "Toss Bank",
    "KB Kookmin",
    "Shinhan Bank",
    "Woori Bank",
    "Hana Bank",
    "NH NongHyup",
    "IBK Industrial Bank",
    "Jeonbuk Bank",
    "Bank Jago",
    "blu by BCA Digital",
    "Cash",
    "Other",
]

INCOME_SOURCES = [
    "Scholarship / stipend",
    "Salary / assistantship",
    "Family transfer / allowance",
    "Refund",
    "Cash deposit",
    "Gift",
    "Other",
]

IMPORT_CATEGORY_DEFAULTS = {
    "Food & Groceries": "Food",
    "Lifestyle & Others": "Other",
    "Housing & Utilities": "Housing",
    "Health & Personal": "Health",
    "Transportation": "Transportation",
}

IMPORT_BANK_DEFAULTS = {
    "Card JB Bank": "Jeonbuk Bank",
    "Card Jago": "Bank Jago",
    "Card Blu": "blu by BCA Digital",
    "Cash": "Cash",
}

IMPORT_REQUIRED_COLUMNS = {
    "expense details",
    "category",
    "cost",
    "transaction date",
    "paid by",
}


def load_supabase_settings():
    """Read Supabase credentials from Streamlit secrets."""
    try:
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        supabase_url = None
        supabase_key = None

    if not supabase_url or not supabase_key:
        st.error("Supabase has not been configured yet.")
        st.code(
            'SUPABASE_URL = "https://your-project.supabase.co"\n'
            'SUPABASE_KEY = "your-publishable-or-anon-key"',
            language="toml",
        )
        st.info(
            "Add these values to .streamlit/secrets.toml locally, or to "
            "Advanced settings → Secrets when deploying on Streamlit Community Cloud."
        )
        st.stop()

    return supabase_url, supabase_key


def get_supabase_client() -> Client:
    """Keep one Supabase client inside this user's Streamlit session."""
    if "supabase_client" not in st.session_state:
        supabase_url, supabase_key = load_supabase_settings()
        st.session_state.supabase_client = create_client(supabase_url, supabase_key)
    return st.session_state.supabase_client


def sign_in(client: Client, email: str, password: str):
    """Authenticate a user and save basic user information in session state."""
    response = client.auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    if not response.user or not response.session:
        raise RuntimeError("Supabase did not return an authenticated session.")

    st.session_state.current_user = {
        "id": response.user.id,
        "email": response.user.email,
    }


def sign_out(client: Client):
    """End the Supabase session and clear the local Streamlit session."""
    try:
        client.auth.sign_out()
    finally:
        for key in ("current_user", "supabase_client"):
            st.session_state.pop(key, None)


def show_login(client: Client):
    """Render a small login page and stop before showing private data."""
    st.title("💸 WonWise")
    st.caption("Your private expense tracker in Korean won")

    left_space, login_column, right_space = st.columns([1, 1.3, 1])
    with login_column:
        st.subheader("Sign in")
        st.write("Use the email and password created in Supabase.")

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Sign in", width="stretch")

        if login_clicked:
            if not email or not password:
                st.warning("Please enter both email and password.")
            else:
                try:
                    sign_in(client, email, password)
                except Exception:
                    st.error("Login failed. Check your email and password.")
                else:
                    # Keep Streamlit's rerun outside the exception handler.
                    # A rerun is an internal control signal, not a login error.
                    st.rerun()

        st.caption("There is no public sign-up. This keeps the app private.")

    st.stop()


def add_expense(client, user_id, expense_date, category, bank, amount, note):
    """Insert one expense. Row Level Security checks the user ID again."""
    client.table("expenses").insert(
        {
            "user_id": user_id,
            "expense_date": expense_date.isoformat(),
            "category": category,
            "bank": bank,
            "amount": int(amount),
            "note": note.strip(),
        }
    ).execute()


def add_tracked_expense(client, account_id, expense_date, category, amount, note):
    """Insert an expense and debit its account atomically in Supabase."""
    client.rpc(
        "wonwise_add_expense",
        {
            "p_account_id": account_id,
            "p_expense_date": expense_date.isoformat(),
            "p_category": category,
            "p_amount": int(amount),
            "p_note": note.strip(),
        },
    ).execute()


def import_expenses(client, user_id, expenses):
    """Insert imported expenses in small batches."""
    rows = []
    for expense in expenses:
        rows.append(
            {
                "user_id": user_id,
                "expense_date": expense["expense_date"],
                "category": expense["category"],
                "bank": expense["bank"],
                "amount": int(expense["amount"]),
                "note": expense["note"],
            }
        )

    for start in range(0, len(rows), 200):
        client.table("expenses").insert(rows[start : start + 200]).execute()


def delete_expense(client, expense_id, balance_features_ready=True):
    """Delete an expense and refund it when it debited a tracked account."""
    if balance_features_ready:
        client.rpc(
            "wonwise_delete_expense",
            {"p_expense_id": expense_id},
        ).execute()
    else:
        client.table("expenses").delete().eq("id", expense_id).execute()


def load_expenses(client):
    """Load the signed-in user's expenses from Supabase."""
    response = (
        client.table("expenses")
        .select("id, expense_date, category, bank, amount, note")
        .order("expense_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )

    columns = ["id", "expense_date", "category", "bank", "amount", "note"]
    expenses = pd.DataFrame(response.data or [], columns=columns)
    if not expenses.empty:
        expenses["expense_date"] = pd.to_datetime(expenses["expense_date"])
        expenses["amount"] = pd.to_numeric(expenses["amount"])
    return expenses


def load_accounts(client):
    """Load current balances for the signed-in user's accounts."""
    response = (
        client.table("accounts")
        .select("id, name, balance")
        .order("name")
        .execute()
    )
    columns = ["id", "name", "balance"]
    accounts = pd.DataFrame(response.data or [], columns=columns)
    if not accounts.empty:
        accounts["balance"] = pd.to_numeric(accounts["balance"]).astype("int64")
    return accounts


def load_account_movements(client):
    """Load the latest balance movements for the signed-in user."""
    response = (
        client.table("account_movements")
        .select("id, account_id, movement_type, amount, note, created_at")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    columns = [
        "id",
        "account_id",
        "movement_type",
        "amount",
        "note",
        "created_at",
    ]
    movements = pd.DataFrame(response.data or [], columns=columns)
    if not movements.empty:
        movements["amount"] = pd.to_numeric(movements["amount"]).astype("int64")
        movements["created_at"] = pd.to_datetime(
            movements["created_at"],
            utc=True,
            errors="coerce",
        )
    return movements


def create_account(client, name, opening_balance):
    """Create a bank, wallet, or cash account with its current balance."""
    client.rpc(
        "wonwise_create_account",
        {
            "p_name": name.strip(),
            "p_opening_balance": int(opening_balance),
        },
    ).execute()


def add_money(client, account_id, amount, note):
    """Add incoming money to one account."""
    client.rpc(
        "wonwise_add_money",
        {
            "p_account_id": account_id,
            "p_amount": int(amount),
            "p_note": note.strip(),
        },
    ).execute()


def set_account_balance(client, account_id, new_balance, note):
    """Correct an account so it matches the real balance."""
    client.rpc(
        "wonwise_set_balance",
        {
            "p_account_id": account_id,
            "p_new_balance": int(new_balance),
            "p_note": note.strip(),
        },
    ).execute()


def transfer_funds(client, from_account_id, to_account_id, amount, note):
    """Move money between two owned accounts without creating an expense."""
    client.rpc(
        "wonwise_transfer_funds",
        {
            "p_from_account_id": from_account_id,
            "p_to_account_id": to_account_id,
            "p_amount": int(amount),
            "p_note": note.strip(),
        },
    ).execute()


def set_flash(message, kind="success"):
    """Keep a short message visible after Streamlit reruns."""
    st.session_state.wonwise_flash = {"message": message, "kind": kind}


def show_flash():
    """Display and clear the latest action message."""
    flash = st.session_state.pop("wonwise_flash", None)
    if not flash:
        return
    if flash["kind"] == "warning":
        st.warning(flash["message"])
    elif flash["kind"] == "error":
        st.error(flash["message"])
    else:
        st.success(flash["message"])


def normalize_column_name(column):
    """Normalize spreadsheet headers so capitalization does not matter."""
    return " ".join(str(column).strip().lower().split())


def parse_import_date(value):
    """Read Excel date cells, Excel serial dates, or written dates."""
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (int, float)):
        return pd.Timestamp("1899-12-30") + pd.to_timedelta(value, unit="D")
    return pd.to_datetime(value, errors="coerce")


def parse_import_amount(value):
    """Turn values such as ₩14,060 into the integer 14060."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    written_value = str(value).strip()
    is_negative = written_value.startswith("-") or (
        written_value.startswith("(") and written_value.endswith(")")
    )
    cleaned = "".join(character for character in written_value if character.isdigit())
    if not cleaned:
        return None
    amount = int(cleaned)
    return -amount if is_negative else amount


def read_expense_workbook(uploaded_file):
    """Combine all monthly sheets that use the user's expense format."""
    uploaded_file.seek(0)
    workbook_sheets = pd.read_excel(uploaded_file, sheet_name=None)
    imported_frames = []
    invalid_frames = []
    used_sheets = []
    ignored_sheets = []

    for sheet_name, source in workbook_sheets.items():
        normalized_columns = {
            normalize_column_name(column): column for column in source.columns
        }
        if not IMPORT_REQUIRED_COLUMNS.issubset(normalized_columns):
            ignored_sheets.append(sheet_name)
            continue

        used_sheets.append(sheet_name)
        frame = pd.DataFrame(
            {
                "details": source[normalized_columns["expense details"]],
                "source_category": source[normalized_columns["category"]],
                "amount": source[normalized_columns["cost"]],
                "expense_date": source[normalized_columns["transaction date"]],
                "source_bank": source[normalized_columns["paid by"]],
                "extra_note": (
                    source[normalized_columns["notes"]]
                    if "notes" in normalized_columns
                    else ""
                ),
            }
        )

        frame = frame[frame["details"].notna()].copy()
        frame["details"] = frame["details"].astype(str).str.strip()
        frame = frame[frame["details"] != ""]
        frame["source_category"] = frame["source_category"].fillna("").astype(str).str.strip()
        frame["source_bank"] = frame["source_bank"].fillna("").astype(str).str.strip()
        frame["extra_note"] = frame["extra_note"].fillna("").astype(str).str.strip()
        frame["amount"] = frame["amount"].map(parse_import_amount)
        frame["expense_date"] = frame["expense_date"].map(parse_import_date)
        frame["source_sheet"] = sheet_name

        invalid = frame[
            frame["expense_date"].isna()
            | frame["amount"].isna()
            | (frame["amount"] <= 0)
            | (frame["source_category"] == "")
            | (frame["source_bank"] == "")
        ].copy()
        valid = frame.drop(index=invalid.index).copy()

        if not valid.empty:
            imported_frames.append(valid)
        if not invalid.empty:
            invalid_frames.append(invalid)

    columns = [
        "details",
        "source_category",
        "amount",
        "expense_date",
        "source_bank",
        "extra_note",
        "source_sheet",
    ]
    imported = (
        pd.concat(imported_frames, ignore_index=True)
        if imported_frames
        else pd.DataFrame(columns=columns)
    )
    invalid = (
        pd.concat(invalid_frames, ignore_index=True)
        if invalid_frames
        else pd.DataFrame(columns=columns)
    )
    return imported, invalid, used_sheets, ignored_sheets


def expense_import_key(expense_date, category, bank, amount, note):
    """Create a stable key used only to avoid duplicate imports."""
    normalized_date = pd.Timestamp(expense_date).date().isoformat()
    normalized_note = "" if pd.isna(note) else str(note).strip().lower()
    return (
        normalized_date,
        str(category).strip().lower(),
        str(bank).strip().lower(),
        int(amount),
        normalized_note,
    )


def prepare_import_rows(imported, category_mapping, bank_mapping, existing_expenses):
    """Apply mappings and remove rows already saved in Supabase."""
    existing_keys = set()
    for _, expense in existing_expenses.iterrows():
        existing_keys.add(
            expense_import_key(
                expense["expense_date"],
                expense["category"],
                expense["bank"],
                expense["amount"],
                expense["note"],
            )
        )

    prepared_rows = []
    duplicate_count = 0
    seen_upload_keys = set()

    for _, expense in imported.iterrows():
        note = expense["details"]
        if expense["extra_note"]:
            note = f"{note} | {expense['extra_note']}"

        prepared = {
            "expense_date": expense["expense_date"].date().isoformat(),
            "category": category_mapping[expense["source_category"]],
            "bank": bank_mapping[expense["source_bank"]],
            "amount": int(expense["amount"]),
            "note": note,
        }
        key = expense_import_key(**prepared)
        if key in existing_keys or key in seen_upload_keys:
            duplicate_count += 1
            continue

        seen_upload_keys.add(key)
        prepared_rows.append(prepared)

    return prepared_rows, duplicate_count


def format_krw(amount):
    """Display an integer amount as Korean won."""
    return f"₩{int(amount):,}"


def month_label(month_key):
    """Convert YYYY-MM into a friendly label."""
    year, month = map(int, month_key.split("-"))
    return f"{calendar.month_name[month]} {year}"


def year_label(year):
    """Label current and previous years while keeping older years readable."""
    current_year = date.today().year
    if year == current_year:
        return f"{year} · This year"
    if year == current_year - 1:
        return f"{year} · Last year"
    return str(year)


def render_added_money_history(movements, accounts, show_balances):
    """Show only entries created through the Add money form."""
    st.markdown("#### Added money history")
    deposits = movements[movements["movement_type"] == "deposit"].copy()
    if deposits.empty:
        st.caption("No money has been added yet.")
        return

    account_names = accounts.set_index("id")["name"].to_dict()
    deposits["Date"] = (
        deposits["created_at"]
        .dt.tz_convert("Asia/Seoul")
        .dt.strftime("%Y-%m-%d %H:%M")
    )
    deposits["Account"] = deposits["account_id"].map(account_names).fillna(
        "Deleted account"
    )
    if show_balances:
        deposits["Amount"] = deposits["amount"].map(format_krw)
    else:
        deposits["Amount"] = "₩••••••"
    deposits["Source / Note"] = deposits["note"].replace("", "—")
    st.dataframe(
        deposits[["Date", "Account", "Amount", "Source / Note"]],
        hide_index=True,
        width="stretch",
    )


def render_account_manager(client, accounts, movements, show_balances):
    """Show balances and simple forms for account money movements."""
    balance_tab, manage_tab = st.tabs(["Balance overview", "Manage balances"])

    with balance_tab:
        st.subheader("Account balances")

        if accounts.empty:
            st.info(
                "No balance account yet. Open Manage balances to create "
                "Jeonbuk Bank, Kakao Pay, cash, or another account."
            )
        else:
            balance_table = accounts[["name", "balance"]].copy()
            if show_balances:
                balance_table["balance"] = balance_table["balance"].map(format_krw)
            else:
                balance_table["balance"] = "₩••••••"
            balance_table = balance_table.rename(
                columns={"name": "Bank / Account", "balance": "Current balance"}
            )
            st.dataframe(balance_table, hide_index=True, width="stretch")

    with manage_tab:
        st.subheader("Manage balances")
        create_tab, add_tab, correct_tab, transfer_tab = st.tabs(
            ["Add account", "Add money", "Correct balance", "Transfer"]
        )

        with create_tab:
            st.caption(
                "Enter the amount currently available in this bank, wallet, or cash."
            )
            with st.form("create_account_form", clear_on_submit=True):
                account_name = st.text_input(
                    "Account name",
                    placeholder="Example: Jeonbuk Bank or Kakao Pay",
                )
                opening_balance = st.number_input(
                    "Current balance (₩)",
                    min_value=0,
                    value=0,
                    step=1_000,
                )
                create_clicked = st.form_submit_button(
                    "Create account", width="stretch"
                )

            if create_clicked:
                if not account_name.strip():
                    st.warning("Please enter an account name.")
                else:
                    try:
                        create_account(client, account_name, opening_balance)
                    except Exception as error:
                        st.error(f"Could not create the account: {error}")
                    else:
                        set_flash(f"Created {account_name.strip()}.")
                        st.rerun()

        with add_tab:
            if accounts.empty:
                st.info("Create an account first.")
            else:
                account_ids = accounts["id"].tolist()
                account_names = accounts.set_index("id")["name"].to_dict()
                with st.form("add_money_form", clear_on_submit=True):
                    deposit_account = st.selectbox(
                        "Add money to",
                        account_ids,
                        format_func=lambda account_id: account_names[account_id],
                    )
                    deposit_amount = st.number_input(
                        "Amount received (₩)",
                        min_value=100,
                        value=10_000,
                        step=1_000,
                    )
                    deposit_source = st.selectbox(
                        "Money source",
                        INCOME_SOURCES,
                    )
                    deposit_details = st.text_input(
                        "Details (optional)",
                        placeholder="Example: September GKS stipend",
                    )
                    deposit_clicked = st.form_submit_button(
                        "Add money", width="stretch"
                    )

                if deposit_clicked:
                    deposit_note = deposit_source
                    if deposit_details.strip():
                        deposit_note = (
                            f"{deposit_source} · {deposit_details.strip()}"
                        )
                    try:
                        add_money(
                            client,
                            deposit_account,
                            deposit_amount,
                            deposit_note,
                        )
                    except Exception as error:
                        st.error(f"Could not add the money: {error}")
                    else:
                        set_flash(
                            f"Added {format_krw(deposit_amount)} to "
                            f"{account_names[deposit_account]}."
                        )
                        st.rerun()

                render_added_money_history(
                    movements,
                    accounts,
                    show_balances,
                )

        with correct_tab:
            if accounts.empty:
                st.info("Create an account first.")
            else:
                account_ids = accounts["id"].tolist()
                account_names = accounts.set_index("id")["name"].to_dict()
                with st.form("correct_balance_form", clear_on_submit=True):
                    corrected_account = st.selectbox(
                        "Account to correct",
                        account_ids,
                        format_func=lambda account_id: account_names[account_id],
                    )
                    corrected_balance = st.number_input(
                        "Actual balance now (₩)",
                        min_value=0,
                        value=0,
                        step=1_000,
                        help="Use the balance shown in your real banking app.",
                    )
                    correction_note = st.text_input(
                        "Reason (optional)",
                        placeholder="Example: starting balance correction",
                    )
                    correct_clicked = st.form_submit_button(
                        "Update balance", width="stretch"
                    )

                if correct_clicked:
                    try:
                        set_account_balance(
                            client,
                            corrected_account,
                            corrected_balance,
                            correction_note,
                        )
                    except Exception as error:
                        st.error(f"Could not update the balance: {error}")
                    else:
                        set_flash(
                            f"{account_names[corrected_account]} is now "
                            f"{format_krw(corrected_balance)}."
                        )
                        st.rerun()

        with transfer_tab:
            if len(accounts) < 2:
                st.info("Create at least two accounts to make a transfer.")
            else:
                account_ids = accounts["id"].tolist()
                account_names = accounts.set_index("id")["name"].to_dict()
                account_balances = accounts.set_index("id")["balance"].to_dict()

                def transfer_account_label(account_id):
                    if show_balances:
                        return (
                            f"{account_names[account_id]} · "
                            f"{format_krw(account_balances[account_id])}"
                        )
                    return account_names[account_id]

                with st.form("transfer_form", clear_on_submit=True):
                    from_account = st.selectbox(
                        "From",
                        account_ids,
                        format_func=transfer_account_label,
                    )
                    to_account = st.selectbox(
                        "To",
                        account_ids,
                        index=1,
                        format_func=transfer_account_label,
                    )
                    transfer_amount = st.number_input(
                        "Transfer amount (₩)",
                        min_value=100,
                        value=10_000,
                        step=1_000,
                    )
                    transfer_note = st.text_input(
                        "Note (optional)",
                        placeholder="Example: Kakao Pay top-up",
                    )
                    transfer_clicked = st.form_submit_button(
                        "Transfer money", width="stretch"
                    )

                if transfer_clicked:
                    if from_account == to_account:
                        st.warning("Choose two different accounts.")
                    else:
                        try:
                            transfer_funds(
                                client,
                                from_account,
                                to_account,
                                transfer_amount,
                                transfer_note,
                            )
                        except Exception as error:
                            st.error(f"Could not transfer the money: {error}")
                        else:
                            set_flash(
                                f"Transferred {format_krw(transfer_amount)} from "
                                f"{account_names[from_account]} to "
                                f"{account_names[to_account]}."
                            )
                            st.rerun()


def render_excel_importer(client, user_id, existing_expenses):
    """Show an importer tailored to the user's multi-sheet expense workbook."""
    with st.expander("Import expenses from Excel"):
        st.write(
            "Upload your existing .xlsx file. Monthly sheets are combined, while "
            "summary sheets and total rows are ignored automatically."
        )
        uploaded_file = st.file_uploader(
            "Expense spreadsheet",
            type=["xlsx"],
            key="expense_workbook",
        )
        if uploaded_file is None:
            return

        try:
            imported, invalid, used_sheets, ignored_sheets = read_expense_workbook(
                uploaded_file
            )
        except Exception as error:
            st.error(f"Could not read this Excel file: {error}")
            return

        if imported.empty:
            st.warning("No valid expense rows were found in this workbook.")
            return

        st.success(
            f"Found {len(imported):,} valid expenses across "
            f"{len(used_sheets)} monthly sheets."
        )
        if ignored_sheets:
            st.caption(
                "Ignored summary sheets: " + ", ".join(ignored_sheets)
            )
        if not invalid.empty:
            row_word = "row" if len(invalid) == 1 else "rows"
            st.warning(
                f"{len(invalid)} {row_word} will be skipped because its date, amount, "
                "category, or payment account is invalid."
            )

        st.markdown("#### Match spreadsheet categories")
        category_mapping = {}
        category_columns = st.columns(2)
        for index, source_category in enumerate(
            sorted(imported["source_category"].unique())
        ):
            default_category = IMPORT_CATEGORY_DEFAULTS.get(source_category, "Other")
            with category_columns[index % 2]:
                category_mapping[source_category] = st.selectbox(
                    source_category,
                    CATEGORIES,
                    index=CATEGORIES.index(default_category),
                    key=f"import_category_{source_category}",
                )

        st.markdown("#### Match payment accounts")
        bank_mapping = {}
        bank_columns = st.columns(2)
        for index, source_bank in enumerate(sorted(imported["source_bank"].unique())):
            default_bank = IMPORT_BANK_DEFAULTS.get(source_bank, "Other")
            with bank_columns[index % 2]:
                bank_mapping[source_bank] = st.selectbox(
                    source_bank,
                    BANKS,
                    index=BANKS.index(default_bank),
                    key=f"import_bank_{source_bank}",
                )

        rows_to_import, duplicate_count = prepare_import_rows(
            imported,
            category_mapping,
            bank_mapping,
            existing_expenses,
        )

        preview = pd.DataFrame(rows_to_import)
        total_amount = sum(row["amount"] for row in rows_to_import)
        metric_1, metric_2, metric_3 = st.columns(3)
        metric_1.metric("Ready to import", f"{len(rows_to_import):,}")
        metric_2.metric("Total", format_krw(total_amount))
        metric_3.metric("Duplicates skipped", f"{duplicate_count:,}")

        if not preview.empty:
            preview["amount"] = preview["amount"].map(format_krw)
            preview = preview.rename(
                columns={
                    "expense_date": "Date",
                    "category": "Category",
                    "bank": "Bank / Account",
                    "amount": "Amount",
                    "note": "Used for / Note",
                }
            )
            st.dataframe(preview.head(30), hide_index=True, width="stretch")
            st.caption("Preview shows the first 30 rows.")

        import_clicked = st.button(
            f"Import {len(rows_to_import):,} expenses",
            type="primary",
            disabled=not rows_to_import,
        )
        if import_clicked:
            try:
                import_expenses(client, user_id, rows_to_import)
            except Exception as error:
                st.error(f"Import failed: {error}")
            else:
                st.success(f"Imported {len(rows_to_import):,} expenses.")
                st.rerun()


def draw_category_charts(category_summary):
    """Show a bar chart and a pie chart for category spending."""
    colors = [
        "#5B8FF9",
        "#61DDAA",
        "#65789B",
        "#F6BD16",
        "#7262FD",
        "#78D3F8",
        "#9661BC",
        "#F6903D",
        "#008685",
        "#F08BB4",
    ]
    bar_tab, pie_tab = st.tabs(["Bar chart", "Pie chart"])

    with bar_tab:
        figure, axis = plt.subplots(figsize=(9, 4.8))
        axis.bar(
            category_summary.index,
            category_summary.values,
            color=colors[: len(category_summary)],
        )
        axis.set_ylabel("Amount (KRW)")
        axis.set_xlabel("")
        axis.tick_params(axis="x", rotation=35)
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        figure.tight_layout()
        st.pyplot(figure)
        plt.close(figure)

    with pie_tab:
        figure, axis = plt.subplots(figsize=(7, 5.2))
        axis.pie(
            category_summary.values,
            labels=category_summary.index,
            autopct="%1.1f%%",
            startangle=90,
            colors=colors[: len(category_summary)],
        )
        axis.set_title("Share of monthly spending")
        figure.tight_layout()
        st.pyplot(figure)
        plt.close(figure)


st.set_page_config(page_title=APP_TITLE, page_icon="💸", layout="wide")
supabase = get_supabase_client()

if "current_user" not in st.session_state:
    show_login(supabase)

current_user = st.session_state.current_user

try:
    accounts = load_accounts(supabase)
    account_movements = load_account_movements(supabase)
    balance_features_ready = True
except Exception:
    accounts = pd.DataFrame(columns=["id", "name", "balance"])
    account_movements = pd.DataFrame(
        columns=[
            "id",
            "account_id",
            "movement_type",
            "amount",
            "note",
            "created_at",
        ]
    )
    balance_features_ready = False

st.title("💸 WonWise")
st.caption("Your private expense tracker in Korean won · synced with Supabase")
show_flash()

spending_visibility_column, balance_visibility_column, refresh_column = st.columns(
    [2, 2, 1]
)
with spending_visibility_column:
    show_yearly_spending = st.toggle(
        "Show yearly spending",
        value=False,
        help="Turn this on to reveal the selected year's total spending.",
    )

with balance_visibility_column:
    if balance_features_ready:
        show_balances = st.toggle(
            "Show account balances",
            value=False,
            help="Turn this off to hide the total and individual account balances.",
        )
    else:
        show_balances = False

with refresh_column:
    refresh_clicked = st.button("↻ Refresh data", width="stretch")

if refresh_clicked:
    set_flash("Data refreshed.")
    st.rerun()

if not balance_features_ready:
    st.warning(
        "Balance and transfer features are not active yet. Run the updated "
        "supabase_schema.sql in Supabase SQL Editor, then refresh this app."
    )

with st.sidebar:
    st.write(f"Signed in as **{current_user['email']}**")
    if st.button("Sign out", width="stretch"):
        sign_out(supabase)
        st.rerun()

    st.divider()
    st.header("Add an expense")

    with st.form("expense_form", clear_on_submit=True):
        expense_date = st.date_input("Date", value=date.today())
        category = st.selectbox("Category", CATEGORIES)

        tracked_account_id = None
        if not accounts.empty:
            account_names = accounts.set_index("id")["name"].to_dict()
            account_balances = accounts.set_index("id")["balance"].to_dict()
            untracked_option = "__wonwise_untracked__"
            payment_options = accounts["id"].tolist() + [untracked_option]

            def payment_option_label(option):
                if option == untracked_option:
                    return "Other payment method (do not change a balance)"
                if show_balances:
                    return (
                        f"{account_names[option]} · "
                        f"{format_krw(account_balances[option])}"
                    )
                return account_names[option]

            selected_payment = st.selectbox(
                "Pay from",
                payment_options,
                format_func=payment_option_label,
            )
            if selected_payment == untracked_option:
                selected_bank = st.selectbox(
                    "Bank / payment account",
                    BANKS,
                )
                custom_bank = st.text_input(
                    "Other bank name (only if you selected Other)",
                    placeholder="Example: another bank",
                )
            else:
                tracked_account_id = selected_payment
                selected_bank = account_names[selected_payment]
                custom_bank = ""
        else:
            selected_bank = st.selectbox("Bank / payment account", BANKS)
            custom_bank = st.text_input(
                "Other bank name (only if you selected Other)",
                placeholder="Example: another bank",
            )

        amount = st.number_input(
            "Amount (₩)",
            min_value=100,
            value=10_000,
            step=1_000,
            help="Enter a whole number, for example 12500.",
        )
        note = st.text_input(
            "Used for / note (optional)",
            placeholder="Example: lunch at the cafeteria",
        )
        submitted = st.form_submit_button("Save expense", width="stretch")

    if submitted:
        bank = custom_bank.strip() if selected_bank == "Other" else selected_bank
        if not bank:
            st.error("Please enter the bank name.")
        else:
            try:
                if tracked_account_id:
                    add_tracked_expense(
                        supabase,
                        tracked_account_id,
                        expense_date,
                        category,
                        amount,
                        note,
                    )
                else:
                    add_expense(
                        supabase,
                        current_user["id"],
                        expense_date,
                        category,
                        bank,
                        amount,
                        note,
                    )
            except Exception as error:
                st.error(f"Could not save the expense: {error}")
            else:
                set_flash(f"Saved {format_krw(amount)} for {category}.")
                st.rerun()

try:
    expenses = load_expenses(supabase)
except Exception:
    st.error(
        "Could not load your expenses. Check the Supabase table, Row Level "
        "Security policies, and Streamlit secrets."
    )
    st.stop()

today = date.today()
if expenses.empty:
    spending_year_options = [today.year]
else:
    saved_years = expenses["expense_date"].dt.year.unique().tolist()
    spending_year_options = sorted(set(saved_years + [today.year]), reverse=True)

selected_spending_year = st.selectbox(
    "Yearly spending",
    spending_year_options,
    format_func=year_label,
)

if expenses.empty:
    selected_year_spending = 0
else:
    selected_year_spending = int(
        expenses.loc[
            expenses["expense_date"].dt.year == selected_spending_year,
            "amount",
        ].sum()
    )

total_balance = int(accounts["balance"].sum()) if not accounts.empty else 0
overview_1, overview_2 = st.columns(2)
overview_1.metric(
    f"Total spending {selected_spending_year}",
    format_krw(selected_year_spending) if show_yearly_spending else "₩••••••",
)
overview_2.metric(
    "Total available balance",
    (
        format_krw(total_balance)
        if balance_features_ready and show_balances
        else "₩••••••" if balance_features_ready else "—"
    ),
)

if balance_features_ready:
    render_account_manager(
        supabase,
        accounts,
        account_movements,
        show_balances,
    )

render_excel_importer(supabase, current_user["id"], expenses)

current_month = date.today().strftime("%Y-%m")
if expenses.empty:
    month_options = [current_month]
else:
    saved_months = expenses["expense_date"].dt.strftime("%Y-%m").unique().tolist()
    month_options = sorted(set(saved_months + [current_month]), reverse=True)

selected_month = st.selectbox(
    "Summary month",
    month_options,
    format_func=month_label,
)

if expenses.empty:
    monthly_expenses = expenses.copy()
else:
    monthly_expenses = expenses[
        expenses["expense_date"].dt.strftime("%Y-%m") == selected_month
    ].copy()

st.subheader(f"Monthly summary · {month_label(selected_month)}")

if monthly_expenses.empty:
    st.info("No expenses for this month yet. Add your first expense from the sidebar.")
else:
    total_spending = int(monthly_expenses["amount"].sum())
    transaction_count = len(monthly_expenses)
    category_summary = (
        monthly_expenses.groupby("category")["amount"].sum().sort_values(ascending=False)
    )
    bank_summary = (
        monthly_expenses.groupby("bank")["amount"].sum().sort_values(ascending=False)
    )

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Total spending", format_krw(total_spending))
    metric_2.metric("Transactions", f"{transaction_count}")
    metric_3.metric("Largest category", category_summary.index[0])

    chart_column, bank_column = st.columns([2, 1])

    with chart_column:
        st.markdown("#### Spending by category")
        draw_category_charts(category_summary)

    with bank_column:
        st.markdown("#### Spending by bank / account")
        bank_table = bank_summary.rename("Amount").reset_index()
        bank_table["Amount"] = bank_table["Amount"].map(format_krw)
        st.dataframe(bank_table, hide_index=True, width="stretch")

    st.markdown("#### Expenses in this month")
    display_table = monthly_expenses.copy()
    display_table["expense_date"] = display_table["expense_date"].dt.strftime("%Y-%m-%d")
    display_table["amount"] = display_table["amount"].map(format_krw)
    display_table = display_table.drop(columns=["id"]).rename(
        columns={
            "expense_date": "Date",
            "category": "Category",
            "bank": "Bank / Account",
            "amount": "Amount",
            "note": "Used for / Note",
        }
    )
    st.dataframe(display_table, hide_index=True, width="stretch")

    with st.expander("Delete an expense"):
        expense_ids = monthly_expenses["id"].tolist()

        def expense_label(expense_id):
            row = monthly_expenses.loc[monthly_expenses["id"] == expense_id].iloc[0]
            return f"{row['expense_date']:%Y-%m-%d} · {row['category']} · {format_krw(row['amount'])}"

        expense_to_delete = st.selectbox(
            "Choose an expense",
            expense_ids,
            format_func=expense_label,
        )
        if st.button("Delete selected expense", type="secondary"):
            try:
                delete_expense(
                    supabase,
                    expense_to_delete,
                    balance_features_ready,
                )
            except Exception as error:
                st.error(f"Could not delete the expense: {error}")
            else:
                set_flash(
                    "Expense deleted. If it used a tracked account, its balance "
                    "was restored."
                )
                st.rerun()

st.divider()
st.caption("Your data is stored securely in your Supabase account.")
