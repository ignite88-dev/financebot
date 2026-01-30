# Telegram AI Group Finance Assistant

Bot AI Telegram untuk manajemen keuangan grup dengan fitur context-aware dan spreadsheet-driven.

## Fitur Utama

- **AI-Powered Responses**: Bot memahami bahasa natural untuk mencatat transaksi
- **Multi-Tenant**: Setiap grup memiliki spreadsheet sendiri
- **Memory System**: Bot mengingat konteks percakapan
- **Persona Customization**: Gaya bicara bot bisa disesuaikan
- **Onboarding Otomatis**: Setup grup via chat
- **Audit Trail**: Semua aktivitas tercatat
- **Admin Panel**: Kelola semua grup dari satu tempat

## Arsitektur

```
app/
├── bot/            # Telegram bot client & handlers
├── core/           # Router, context builder, AI engine
├── sheets/         # Google Sheets integration
├── memory/         # Conversation memory management
├── persona/        # Bot persona & style
├── onboarding/     # Group setup flow
├── admin/          # Admin panel & reports
├── config/         # Settings & constants
└── infra/          # Logger, exceptions, utils
```

## Prerequisites

- Python 3.11+
- Google Cloud Service Account
- Telegram Bot Token
- OpenAI API Key

## Instalasi

1. **Clone repository**
```bash
git clone <repository-url>
cd financebot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# atau
venv\Scripts\activate     # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup environment**
```bash
cp .env.example .env
# Edit .env dengan konfigurasi Anda
```

5. **Setup Google Service Account**
   - Buka [Google Cloud Console](https://console.cloud.google.com)
   - Buat project baru atau gunakan yang ada
   - Enable Google Sheets API dan Google Drive API
   - Buat Service Account dan download credentials JSON
   - Simpan sebagai `credentials.json`

6. **Setup Master Spreadsheet**
   - Buat Google Spreadsheet baru
   - Share ke email service account
   - Copy spreadsheet ID ke `.env`

## Konfigurasi

Edit file `.env`:

```env
TELEGRAM_TOKEN=your_bot_token
GOOGLE_CREDENTIALS_PATH=credentials.json
SERVICE_ACCOUNT_EMAIL=your-sa@project.iam.gserviceaccount.com
MASTER_SHEET_ID=your_spreadsheet_id
OPENAI_API_KEY=your_openai_key
SUPER_ADMIN_IDS=your_telegram_id
```

## Menjalankan Bot

```bash
python -m app.main
```

Atau dengan logging ke file:
```bash
LOG_FILE=logs/bot.log python -m app.main
```

## Perintah Bot

### Perintah Dasar
- `/start` - Mulai bot
- `/help` - Tampilkan bantuan
- `/setup` - Setup grup baru
- `/status` - Status grup

### Keuangan
- `/balance` - Cek saldo
- `/add [tipe] [jumlah] [keterangan]` - Tambah transaksi
- `/report [period]` - Laporan keuangan
- `/export` - Link ke spreadsheet

### Pengaturan
- `/settings` - Pengaturan grup
- `/persona` - Ubah persona bot
- `/memory` - Kelola memory

### Contoh Penggunaan

```
/add masuk 1000000 Iuran bulanan
/add keluar 500000 Beli peralatan
/report month
```

Atau dengan bahasa natural:
```
@bot terima iuran 500rb dari pak budi
@bot bayar listrik 150 ribu
@bot berapa saldo kita?
```

## Struktur Spreadsheet

### Master Sheet
- `GROUPS` - Daftar grup terdaftar
- `SUPER_ADMINS` - Admin sistem
- `GLOBAL_SETTINGS` - Pengaturan global
- `PERSONAS` - Daftar persona
- `SYSTEM_LOG` - Log sistem

### Per-Group Sheet
- `CONFIG` - Konfigurasi grup
- `USERS` - Data anggota
- `TRANSACTIONS` - Transaksi
- `JOURNAL` - Catatan
- `AI_MEMORY` - Konteks AI
- `AUDIT_LOG` - Jejak aktivitas

## Development

### Menjalankan Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black app/
isort app/
```

### Type Checking
```bash
mypy app/
```

## Troubleshooting

### Bot tidak merespons
1. Pastikan bot sudah di-add ke grup
2. Pastikan bot adalah admin grup
3. Cek log untuk error

### Spreadsheet error
1. Pastikan service account punya akses
2. Cek credentials.json valid
3. Pastikan API enabled di Google Cloud

### AI tidak merespons
1. Cek OpenAI API key valid
2. Cek quota API tidak habis
3. Cek log untuk error rate limit

## License

MIT License
