# WonWise Expense Tracker — Online Version

WonWise adalah aplikasi Streamlit untuk mencatat pengeluaran dalam Korean won (KRW). Versi ini menggunakan:

- **Supabase Auth** untuk login email dan password.
- **Supabase Database** agar data tetap tersimpan secara online.
- **Row Level Security (RLS)** agar setiap akun hanya dapat mengakses datanya sendiri.
- **Streamlit Community Cloud** agar aplikasi bisa dibuka dari HP kapan saja.

## Fitur

- Tambah pengeluaran berdasarkan tanggal, kategori, bank/payment account, jumlah, dan catatan.
- Ringkasan bulanan dalam KRW.
- Bar chart dan pie chart berdasarkan kategori.
- Ringkasan pengeluaran berdasarkan bank/account.
- Login, logout, dan hapus transaksi.
- Tampilan responsif untuk browser HP.

## File penting

```text
expense_tracker/
├── app.py
├── requirements.txt
├── supabase_schema.sql
├── .streamlit/
│   └── secrets.toml.example
└── README.md
```

## 1. Buat project Supabase

1. Buka https://supabase.com/dashboard dan buat project baru.
2. Setelah project siap, buka **SQL Editor**.
3. Salin seluruh isi `supabase_schema.sql`, tempel ke SQL Editor, lalu tekan **Run**.
4. Buka **Authentication → Users → Add user → Create new user**.
5. Masukkan email dan password yang akan kamu gunakan untuk login.

Tidak ada tombol daftar pada aplikasi. Akun dibuat dari dashboard Supabase supaya aplikasi tetap private.

## 2. Ambil Supabase URL dan key

Di dashboard Supabase, buka **Project Settings → API** atau **Connect**.

Ambil:

- Project URL.
- Publishable key atau legacy `anon` key.

Jangan menggunakan `service_role` atau secret key di aplikasi.

## 3. Jalankan di komputer

Buat file `.streamlit/secrets.toml` dengan menyalin `secrets.toml.example`, kemudian ganti nilainya:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
```

File asli `secrets.toml` sudah masuk `.gitignore`, jadi jangan di-upload ke GitHub.

Install dan jalankan:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 4. Upload ke GitHub

1. Buat repository baru di GitHub, misalnya `wonwise-expense-tracker`.
2. Upload `app.py`, `requirements.txt`, `supabase_schema.sql`, folder `.streamlit` yang hanya berisi `secrets.toml.example`, dan `README.md`.
3. Pastikan file `.streamlit/secrets.toml` yang berisi key asli tidak ikut ter-upload.

## 5. Deploy ke Streamlit Community Cloud

1. Buka https://share.streamlit.io dan login menggunakan GitHub.
2. Klik **Create app**.
3. Pilih repository dan branch GitHub tadi.
4. Isi main file path dengan `app.py`.
5. Buka **Advanced settings → Secrets**.
6. Masukkan:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
```

7. Klik **Deploy**.

Setelah selesai, Streamlit memberikan URL publik. Orang lain bisa melihat halaman login, tetapi mereka tidak bisa membaca data tanpa akun yang valid. RLS di Supabase tetap melindungi setiap baris data.

## 6. Tambahkan ke layar utama iPhone

1. Buka URL Streamlit melalui **Safari**.
2. Tekan tombol **Share**.
3. Pilih **Add to Home Screen**.
4. Beri nama `WonWise`, lalu tekan **Add**.

Ikon WonWise akan muncul di Home Screen. Aplikasi tetap membutuhkan koneksi internet.

## Catatan keamanan

- Jangan commit `.streamlit/secrets.toml`.
- Jangan memakai Supabase secret key atau `service_role` key.
- Gunakan password yang kuat.
- Untuk menambahkan pengguna baru, buat akunnya dari Supabase Authentication.
