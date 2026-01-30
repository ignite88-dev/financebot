# path: app/config/constants.py
"""
Constants - Application-wide constants and text templates.
"""

VERSION = "1.0.0"
APP_NAME = "Finance Assistant Bot"

WELCOME_TEXT = """
<b>Selamat datang di Finance Assistant! 🎉</b>

Saya adalah bot AI yang akan membantu mengelola keuangan grup Anda.

<b>Untuk memulai:</b>
1. Pastikan saya adalah admin grup
2. Ketik /setup untuk memulai konfigurasi
3. Ikuti instruksi yang diberikan

Ketik /help untuk melihat semua perintah.
"""

HELP_TEXT = """
<b>📖 Panduan Finance Assistant</b>

<b>Perintah Dasar:</b>
/start - Mulai bot
/help - Tampilkan bantuan ini
/setup - Setup grup baru
/status - Status grup

<b>Keuangan:</b>
/balance - Cek saldo
/add [tipe] [jumlah] [keterangan] - Tambah transaksi
/report [period] - Laporan keuangan
/export - Export ke spreadsheet

<b>Pengaturan:</b>
/settings - Pengaturan grup
/persona - Ubah persona bot
/memory - Kelola memory bot

<b>Contoh:</b>
• <code>/add masuk 1000000 Iuran bulanan</code>
• <code>/add keluar 500000 Beli peralatan</code>
• <code>/report month</code>

<b>Tips:</b>
Anda juga bisa berbicara dengan saya secara natural!
Cukup mention saya dan tanyakan apa saja tentang keuangan grup.
"""

ADMIN_HELP_TEXT = """
<b>🔧 Admin Commands</b>

<b>Statistik:</b>
/admin - Panel admin
/adminstats - Statistik sistem
/adminlogs - System logs

<b>Grup Management:</b>
/admingroups - Daftar grup
/groupinfo [chat_id] - Info detail grup
/suspend [chat_id] [reason] - Suspend grup
/reactivate [chat_id] - Aktifkan grup
/inactive [days] - Grup tidak aktif

<b>Admin Management:</b>
/addadmin [user_id] [username] - Tambah super admin
/adminsettings - Global settings

<b>Reports:</b>
/systemreport - Laporan sistem
/financialreport - Ringkasan keuangan semua grup
"""

SETUP_INSTRUCTIONS = """
<b>🔧 Setup Finance Assistant</b>

Saya akan membantu Anda menyiapkan sistem keuangan untuk grup ini.

<b>Yang akan dilakukan:</b>
1. Membuat atau menghubungkan Google Spreadsheet
2. Menyiapkan struktur data keuangan
3. Mengkonfigurasi bot untuk grup ini

<b>Yang Anda butuhkan:</b>
• Akun Google (untuk spreadsheet)
• Hak admin di grup ini

Klik tombol di bawah untuk melanjutkan.
"""

ERROR_MESSAGES = {
    "not_admin": "Anda harus menjadi admin grup untuk melakukan ini.",
    "not_setup": "Grup ini belum di-setup. Jalankan /setup terlebih dahulu.",
    "not_active": "Grup ini tidak aktif. Hubungi admin.",
    "invalid_amount": "Jumlah tidak valid. Gunakan angka saja.",
    "invalid_type": "Tipe transaksi tidak valid. Gunakan: masuk/keluar atau income/expense",
    "no_permission": "Anda tidak memiliki izin untuk melakukan ini.",
    "rate_limited": "Terlalu banyak permintaan. Tunggu sebentar.",
    "api_error": "Terjadi kesalahan. Silakan coba lagi.",
    "sheet_error": "Gagal mengakses spreadsheet. Periksa konfigurasi.",
    "not_found": "Data tidak ditemukan."
}

SUCCESS_MESSAGES = {
    "transaction_added": "Transaksi berhasil dicatat!",
    "setup_complete": "Setup berhasil! Grup Anda siap digunakan.",
    "settings_updated": "Pengaturan berhasil diperbarui.",
    "persona_changed": "Persona bot telah diubah.",
    "memory_cleared": "Memory percakapan telah dihapus."
}

TRANSACTION_TYPES = {
    "income": ["masuk", "pemasukan", "income", "in", "terima", "received"],
    "expense": ["keluar", "pengeluaran", "expense", "out", "bayar", "beli", "spent"]
}

DEFAULT_CATEGORIES = {
    "income": [
        "Iuran",
        "Donasi",
        "Penjualan",
        "Pengembalian",
        "Lainnya"
    ],
    "expense": [
        "Operasional",
        "Peralatan",
        "Konsumsi",
        "Transport",
        "Acara",
        "Sewa",
        "Utilitas",
        "Lainnya"
    ]
}

PERSONA_STYLES = {
    "professional": {
        "name": "Profesional",
        "description": "Formal dan bisnis",
        "emoji": "👔"
    },
    "friendly": {
        "name": "Ramah",
        "description": "Casual dan friendly",
        "emoji": "😊"
    },
    "efficient": {
        "name": "Efisien",
        "description": "Singkat dan to the point",
        "emoji": "🎯"
    },
    "motivational": {
        "name": "Motivasional",
        "description": "Penuh semangat",
        "emoji": "🌟"
    }
}

REPORT_PERIODS = {
    "day": {"label": "Hari Ini", "days": 1},
    "week": {"label": "Minggu Ini", "days": 7},
    "month": {"label": "Bulan Ini", "days": 30},
    "quarter": {"label": "Kuartal Ini", "days": 90},
    "year": {"label": "Tahun Ini", "days": 365}
}

CURRENCIES = {
    "IDR": {"symbol": "Rp", "name": "Rupiah", "decimal": 0},
    "USD": {"symbol": "$", "name": "US Dollar", "decimal": 2},
    "EUR": {"symbol": "€", "name": "Euro", "decimal": 2},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar", "decimal": 2}
}

LANGUAGES = {
    "id": {"name": "Bahasa Indonesia", "flag": "🇮🇩"},
    "en": {"name": "English", "flag": "🇺🇸"}
}

MAX_MESSAGE_LENGTH = 4096
MAX_TRANSACTION_DESCRIPTION = 500
MAX_GROUP_NAME_LENGTH = 128
MAX_CATEGORY_NAME_LENGTH = 50

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_TRANSACTIONS = 10

CACHE_TTL_SECONDS = 30
MEMORY_MAX_ENTRIES = 100
CONTEXT_WINDOW_SIZE = 10

SHEET_NAMES = [
    "CONFIG",
    "USERS",
    "TRANSACTIONS",
    "JOURNAL",
    "AI_MEMORY",
    "AUDIT_LOG",
    "CATEGORIES",
    "BUDGETS"
]

MASTER_SHEET_NAMES = [
    "GROUPS",
    "SUPER_ADMINS",
    "GLOBAL_SETTINGS",
    "PERSONAS",
    "SYSTEM_LOG"
]
