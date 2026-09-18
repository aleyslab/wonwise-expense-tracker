# WonWise Expense Tracker

WonWise is a simple private expense tracker for Korean won (KRW), built with
Streamlit and Supabase. It can be opened from a phone or computer.

## Features

- Private email and password login with Supabase Auth.
- Add expenses with a date, category, payment account, amount, and note.
- Select any available year and show its total spending.
- Show the current balance of each bank account, wallet, or cash account.
- Hide or reveal balance values with a privacy toggle.
- Hide or reveal yearly spending independently with its own privacy toggle.
- Add incoming money, correct a balance, and transfer money between accounts.
- Classify incoming money as scholarship, salary, family transfer, refund, and
  other common sources.
- Review the latest account movements in a Money history table.
- Refresh all displayed data without signing out or closing the app.
- Automatically subtract new expenses from the selected tracked account.
- Automatically restore the balance when a tracked expense is deleted.
- Monthly bar chart and pie chart for spending by category.
- Monthly spending summary by bank or payment account.
- Import multiple monthly sheets from an Excel workbook.
- Preview imported rows, map categories and accounts, and skip duplicates.
- Row Level Security so each user can only access their own data.

## Project files

```text
wonwise-expense-tracker/
├── app.py
├── requirements.txt
├── supabase_schema.sql
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example
└── README.md
```

## 1. Set up Supabase

1. Open the [Supabase Dashboard](https://supabase.com/dashboard) and create a
   project.
2. Open **SQL Editor** and create a new query.
3. Copy the complete contents of `supabase_schema.sql` into the query.
4. Click **Run**.
5. Open **Authentication → Users → Add user → Create new user**.
6. Enter the email and password that will be used to sign in to WonWise.

If an older version of WonWise is already installed, run the complete updated
SQL file again. It adds the balance and transfer features without deleting
existing expense data.

## 2. Get the Supabase URL and key

Open **Project Settings → API**, or use the **Connect** button in Supabase.
Copy:

- The project URL.
- The publishable key or legacy `anon` key.

Do not use the secret key or `service_role` key in this application.

## 3. Configure secrets locally

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then enter
the real values:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
```

The real `secrets.toml` file is excluded by `.gitignore` and must not be
uploaded to GitHub.

Install and start the application:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 4. Upload the project to GitHub

1. Open the GitHub repository.
2. Click **Add file → Upload files**.
3. Upload the extracted project files, especially `app.py`,
   `supabase_schema.sql`, `requirements.txt`, and `README.md`.
4. Do not upload only the ZIP file.
5. Click **Commit changes**.

Open `app.py` on GitHub and search for `Spending this month`. If the text is
present, the updated application file has been uploaded successfully.

## 5. Deploy with Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io) and sign in
   with GitHub.
2. Create an app from the WonWise repository and the `main` branch.
3. Set the main file path to `app.py`.
4. Open **Advanced settings → Secrets** and add:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
```

5. Deploy the app.

After a GitHub update, Streamlit normally redeploys automatically. If the old
version remains visible, open the app menu and select **Reboot app**.

Inside WonWise, use **Refresh data** whenever you want to reload expenses,
balances, yearly totals, and money history without signing out.

## 6. Set up account balances

1. Sign in to WonWise.
2. Open **Manage balances and transfer money**.
3. Use **Add account** to create accounts such as `Jeonbuk Bank` and
   `Kakao Pay`.
4. Enter the amount currently available in each real account.
5. Use **Add money** for income such as salary or an external cash top-up.
6. Use **Correct balance** when WonWise does not match the real banking app.
7. Use **Transfer** to move money between accounts. Transfers are not counted
   as spending.

When adding a new expense, select an account under **Pay from**. The expense
will automatically reduce that account's balance.

Balance values are hidden by default. Turn on **Show account balances** to
reveal the total balance, individual account balances, and balances in payment
account selectors.

The selected year's total spending is also hidden by default. Turn on
**Show yearly spending** to reveal it without showing any account balances.

When adding money, choose its source and optionally enter more details. Open
**Money history** to review incoming money, expenses, corrections, refunds, and
transfers. Money moved between your own accounts should be entered through the
**Transfer** tab, not **Add money**, so the total balance stays correct.

## 7. Import historical expenses from Excel

1. Open **Import expenses from Excel** inside WonWise.
2. Upload an `.xlsx` workbook containing these columns:
   `Expense details`, `Category`, `Cost`, `Transaction date`, and `Paid by`.
3. Review the category and payment-account mappings.
4. Review the preview and click **Import expenses**.

WonWise combines compatible monthly sheets, ignores summary sheets and total
rows, and skips expenses that already exist.

Imported expenses are treated as historical records. They appear in monthly
and yearly spending totals according to their dates, but they do not reduce the
current account balances. Enter each account's real current balance separately.

## 8. Add WonWise to an iPhone Home Screen

1. Open the deployed Streamlit URL in Safari.
2. Tap **Share**.
3. Select **Add to Home Screen**.
4. Enter the name `WonWise` and tap **Add**.

An internet connection is required to use the application.

## Security notes

- Never commit `.streamlit/secrets.toml`.
- Never use the Supabase secret key or `service_role` key in Streamlit.
- Use a strong password.
- Create new users from Supabase Authentication when access is required.

## Troubleshooting expense deletion

If deleting an expense shows `permission denied for table account_movements`,
run `fix_delete_permission.sql` once in the Supabase SQL Editor. The delete
function verifies that the expense belongs to the signed-in user before it
deletes the expense or restores a tracked balance.
