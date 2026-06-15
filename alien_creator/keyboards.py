from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

CREATE = "➕ ساخت کانفیگ"
SETTINGS = "⚙️ تنظیمات"
STATUS = "🔌 بررسی اتصال"
CANCEL = "لغو"
CONFIRM = "✅ تایید و ساخت"
MODE_HOLD = "⏸ شروع از اولین اتصال"
MODE_DATE = "📅 تاریخ‌دار از زمان ساخت"
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
        [[KeyboardButton(MODE_HOLD)], [KeyboardButton(MODE_DATE)], [KeyboardButton(CANCEL)]],
        resize_keyboard=True,
    )


def confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONFIRM)], [KeyboardButton(CANCEL)]],
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

