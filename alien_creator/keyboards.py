from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CREATE = "➕ ساخت کانفیگ"
SETTINGS = "⚙️ تنظیمات"
STATUS = "🔌 بررسی اتصال"
CANCEL = "لغو"
CONFIRM = "✅ تایید و ساخت"
USE_DEFAULT = "✅ استفاده از پیش‌فرض"
YES = "بله"
NO = "خیر"
MODE_HOLD = "⏸ شروع از اولین اتصال"
MODE_DATE = "📅 تاریخ‌دار از زمان ساخت"
MODE_UNLIMITED = "♾ زمان نامحدود"
PANEL_ALIEN = "👽 Alien"
PANEL_EASY = "⚡ آسان پنل"
PANEL_MEXICO_HAJMI = "🇲🇽 Mexico Hajmi"
PANEL_MEXICO_NAMAHDOD = "🇲🇽 Mexico Namahdod"
BACK = "بازگشت"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(CREATE)],
            [KeyboardButton(SETTINGS), KeyboardButton(STATUS)],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(CANCEL)]], resize_keyboard=True)


def mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MODE_HOLD)], [KeyboardButton(MODE_DATE)], [KeyboardButton(MODE_UNLIMITED)], [KeyboardButton(CANCEL)]],
        resize_keyboard=True,
    )


def panel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(PANEL_ALIEN)],
            [KeyboardButton(PANEL_EASY)],
            [KeyboardButton(PANEL_MEXICO_HAJMI)],
            [KeyboardButton(PANEL_MEXICO_NAMAHDOD)],
            [KeyboardButton(CANCEL)],
        ],
        resize_keyboard=True,
    )


def confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONFIRM)], [KeyboardButton(CANCEL)]],
        resize_keyboard=True,
    )


def default_or_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(USE_DEFAULT)], [KeyboardButton(CANCEL)]],
        resize_keyboard=True,
    )


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(YES), KeyboardButton(NO)], [KeyboardButton(CANCEL)]],
        resize_keyboard=True,
    )


def inbound_keyboard(
    inbounds: dict[str, list[dict]],
    selected: dict[str, list[str]],
) -> InlineKeyboardMarkup:
    rows = []
    for protocol, entries in sorted(inbounds.items()):
        selected_tags = set(selected.get(protocol, []))
        for entry in entries:
            tag = entry["tag"]
            checked = "✅" if tag in selected_tags else "⬜️"
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{checked} {protocol.upper()} | {tag}",
                        callback_data=f"inbound:{protocol}:{tag}",
                    )
                ]
            )
    rows.append([InlineKeyboardButton("همه", callback_data="inbound:all")])
    rows.append([InlineKeyboardButton("هیچ‌کدام", callback_data="inbound:none")])
    rows.append([InlineKeyboardButton("ذخیره", callback_data="inbound:save")])
    return InlineKeyboardMarkup(rows)


def settings_panel_keyboard(panels: dict[str, str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"settings_panel:{key}")]
        for key, label in panels.items()
    ]
    return InlineKeyboardMarkup(rows)


def easy_panel_settings_keyboard(panel_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("تنظیم گروه‌ها", callback_data=f"easy_settings:{panel_key}:groups")],
            [InlineKeyboardButton("تنظیم HWID", callback_data=f"easy_settings:{panel_key}:hwid")],
            [InlineKeyboardButton("بازگشت", callback_data="settings_back")],
        ]
    )
