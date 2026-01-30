# path: app/onboarding/states.py
"""
Onboarding States - State definitions and data structures.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


class OnboardingState(Enum):
    """Onboarding state enum."""
    WELCOME = "welcome"
    SHARE_SHEET = "share_sheet"
    CREATE_SHEET = "create_sheet"
    VALIDATE_ACCESS = "validate_access"
    INIT_TEMPLATE = "init_template"
    REGISTER_ADMIN = "register_admin"
    ACTIVATE_GROUP = "activate_group"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StateData:
    """Data associated with an onboarding session."""
    chat_id: int
    chat_title: str
    admin_user_id: int
    admin_username: str
    current_state: OnboardingState = OnboardingState.WELCOME

    spreadsheet_id: Optional[str] = None
    spreadsheet_url: Optional[str] = None

    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "admin_user_id": self.admin_user_id,
            "admin_username": self.admin_username,
            "current_state": self.current_state.value,
            "spreadsheet_id": self.spreadsheet_id,
            "spreadsheet_url": self.spreadsheet_url,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateData":
        """Create from dictionary."""
        return cls(
            chat_id=data["chat_id"],
            chat_title=data["chat_title"],
            admin_user_id=data["admin_user_id"],
            admin_username=data["admin_username"],
            current_state=OnboardingState(data.get("current_state", "welcome")),
            spreadsheet_id=data.get("spreadsheet_id"),
            spreadsheet_url=data.get("spreadsheet_url"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=data.get("metadata", {})
        )

    def is_complete(self) -> bool:
        """Check if onboarding is complete."""
        return self.current_state == OnboardingState.COMPLETED

    def has_error(self) -> bool:
        """Check if there's an error."""
        return self.error is not None or self.current_state == OnboardingState.ERROR

    def is_active(self) -> bool:
        """Check if onboarding is active (not completed, not cancelled)."""
        return self.current_state not in [
            OnboardingState.COMPLETED,
            OnboardingState.CANCELLED,
            OnboardingState.ERROR
        ]

    def get_progress(self) -> float:
        """Get progress percentage (0-100)."""
        state_order = [
            OnboardingState.WELCOME,
            OnboardingState.SHARE_SHEET,
            OnboardingState.CREATE_SHEET,
            OnboardingState.VALIDATE_ACCESS,
            OnboardingState.INIT_TEMPLATE,
            OnboardingState.REGISTER_ADMIN,
            OnboardingState.ACTIVATE_GROUP,
            OnboardingState.COMPLETED
        ]

        try:
            current_index = state_order.index(self.current_state)
            return (current_index / (len(state_order) - 1)) * 100
        except ValueError:
            return 0

    def get_next_state(self) -> Optional[OnboardingState]:
        """Get the next expected state."""
        transitions = {
            OnboardingState.WELCOME: OnboardingState.SHARE_SHEET,
            OnboardingState.SHARE_SHEET: OnboardingState.VALIDATE_ACCESS,
            OnboardingState.CREATE_SHEET: OnboardingState.INIT_TEMPLATE,
            OnboardingState.VALIDATE_ACCESS: OnboardingState.INIT_TEMPLATE,
            OnboardingState.INIT_TEMPLATE: OnboardingState.REGISTER_ADMIN,
            OnboardingState.REGISTER_ADMIN: OnboardingState.ACTIVATE_GROUP,
            OnboardingState.ACTIVATE_GROUP: OnboardingState.COMPLETED
        }
        return transitions.get(self.current_state)


class StateTransition:
    """Represents a state transition."""

    VALID_TRANSITIONS = {
        OnboardingState.WELCOME: [OnboardingState.SHARE_SHEET],
        OnboardingState.SHARE_SHEET: [
            OnboardingState.CREATE_SHEET,
            OnboardingState.VALIDATE_ACCESS
        ],
        OnboardingState.CREATE_SHEET: [
            OnboardingState.INIT_TEMPLATE,
            OnboardingState.ERROR
        ],
        OnboardingState.VALIDATE_ACCESS: [
            OnboardingState.INIT_TEMPLATE,
            OnboardingState.SHARE_SHEET,
            OnboardingState.ERROR
        ],
        OnboardingState.INIT_TEMPLATE: [
            OnboardingState.REGISTER_ADMIN,
            OnboardingState.ERROR
        ],
        OnboardingState.REGISTER_ADMIN: [
            OnboardingState.ACTIVATE_GROUP,
            OnboardingState.ERROR
        ],
        OnboardingState.ACTIVATE_GROUP: [
            OnboardingState.COMPLETED,
            OnboardingState.ERROR
        ]
    }

    @classmethod
    def is_valid(
        cls,
        from_state: OnboardingState,
        to_state: OnboardingState
    ) -> bool:
        """Check if a transition is valid."""
        if to_state == OnboardingState.CANCELLED:
            return True

        valid_targets = cls.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets

    @classmethod
    def get_valid_transitions(
        cls,
        from_state: OnboardingState
    ) -> list:
        """Get valid transitions from a state."""
        return cls.VALID_TRANSITIONS.get(from_state, [])


STATE_MESSAGES = {
    OnboardingState.WELCOME: {
        "title": "Selamat Datang",
        "message": (
            "Selamat datang di Finance Assistant! 🎉\n\n"
            "Saya akan membantu Anda menyiapkan sistem keuangan untuk grup ini.\n\n"
            "Klik 'Lanjutkan' untuk memulai setup."
        ),
        "buttons": [
            {"text": "Lanjutkan", "callback": "onboarding:continue"}
        ]
    },
    OnboardingState.SHARE_SHEET: {
        "title": "Spreadsheet",
        "message": (
            "Pilih salah satu opsi:\n\n"
            "1. <b>Buat Baru</b> - Saya akan membuat spreadsheet baru untuk grup ini\n\n"
            "2. <b>Gunakan Existing</b> - Kirim link Google Spreadsheet yang sudah ada\n"
            "   (Pastikan sudah di-share ke email service account bot)"
        ),
        "buttons": [
            {"text": "📄 Buat Spreadsheet Baru", "callback": "onboarding:create_new"},
            {"text": "🔗 Gunakan Spreadsheet Existing", "callback": "onboarding:use_existing"}
        ]
    },
    OnboardingState.CREATE_SHEET: {
        "title": "Membuat Spreadsheet",
        "message": "Sedang membuat spreadsheet baru...",
        "buttons": []
    },
    OnboardingState.VALIDATE_ACCESS: {
        "title": "Validasi Akses",
        "message": "Memvalidasi akses ke spreadsheet...",
        "buttons": []
    },
    OnboardingState.INIT_TEMPLATE: {
        "title": "Inisialisasi",
        "message": "Menyiapkan template dan struktur data...",
        "buttons": []
    },
    OnboardingState.REGISTER_ADMIN: {
        "title": "Registrasi",
        "message": "Mendaftarkan grup ke sistem...",
        "buttons": []
    },
    OnboardingState.ACTIVATE_GROUP: {
        "title": "Aktivasi",
        "message": "Mengaktifkan grup...",
        "buttons": []
    },
    OnboardingState.COMPLETED: {
        "title": "Setup Selesai",
        "message": (
            "Setup selesai! ✅\n\n"
            "Grup Anda sudah siap menggunakan Finance Assistant.\n\n"
            "<b>Langkah selanjutnya:</b>\n"
            "• Ketik /help untuk melihat perintah\n"
            "• Mulai catat transaksi dengan /add\n"
            "• Cek saldo dengan /balance\n\n"
            "Selamat menggunakan! 🎊"
        ),
        "buttons": [
            {"text": "📋 Lihat Spreadsheet", "callback": "onboarding:view_sheet"},
            {"text": "❓ Bantuan", "callback": "help:main"}
        ]
    },
    OnboardingState.ERROR: {
        "title": "Error",
        "message": "Terjadi kesalahan saat setup. Silakan coba lagi.",
        "buttons": [
            {"text": "🔄 Coba Lagi", "callback": "onboarding:retry"},
            {"text": "❌ Batalkan", "callback": "onboarding:cancel"}
        ]
    },
    OnboardingState.CANCELLED: {
        "title": "Dibatalkan",
        "message": "Setup dibatalkan. Jalankan /setup untuk memulai lagi.",
        "buttons": []
    }
}


def get_state_message(state: OnboardingState) -> Dict[str, Any]:
    """Get the message configuration for a state."""
    return STATE_MESSAGES.get(state, {
        "title": "Unknown",
        "message": "State tidak dikenal.",
        "buttons": []
    })
