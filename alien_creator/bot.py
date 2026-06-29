from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import RetryAfter
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .config import Config
from .keyboards import (
    CANCEL,
    CONFIRM,
    CREATE,
    MODE_DATE,
    MODE_HOLD,
    MODE_UNLIMITED,
    PANEL_ALIEN,
    PANEL_EASY,
    PANEL_MEXICO_HAJMI,
    PANEL_MEXICO_NAMAHDOD,
    SETTINGS,
    STATUS,
    USE_DEFAULT,
    cancel_keyboard,
    confirm_keyboard,
    default_or_cancel_keyboard,
    easy_panel_settings_keyboard,
    inbound_keyboard,
    main_keyboard,
    mode_keyboard,
    panel_keyboard,
    settings_panel_keyboard,
)
from .marzban import CreateSpec, MarzbanClient, MarzbanError
from .naming import build_sequence
from .storage import SettingsStore

logger = logging.getLogger(__name__)

PANEL, MODE, VOLUME, DAYS, HWID, SEED, COUNT, REVIEW = range(8)

EASY_PANEL_KEYS = {"easy", "mexico_hajmi", "mexico_namahdod"}
PANEL_BUTTONS = {
    PANEL_ALIEN: "alien",
    PANEL_EASY: "easy",
    PANEL_MEXICO_HAJMI: "mexico_hajmi",
    PANEL_MEXICO_NAMAHDOD: "mexico_namahdod",
}
PANEL_LABELS = {
    "alien": "Alien",
    "easy": "آسان پنل",
    "mexico_hajmi": "Mexico Hajmi",
    "mexico_namahdod": "Mexico Namahdod",
}


def _configured_panel_labels(services: "Services") -> dict[str, str]:
    return {
        key: PANEL_LABELS.get(key, key)
        for key in ("alien", "easy", "mexico_hajmi", "mexico_namahdod")
        if key in services.panels
    }


async def _apply_easy_panel_settings(services: "Services", panel_key: str) -> dict:
    panel = services.panel(panel_key)
    settings = await services.store.get(f"panel_settings:{panel_key}", {})
    if panel_key in EASY_PANEL_KEYS and hasattr(panel, "update_settings"):
        group_ids = settings.get("group_ids")
        hwid_limit = settings.get("hwid_limit", ...)
        kwargs = {}
        if isinstance(group_ids, list) and group_ids:
            kwargs["group_ids"] = [int(item) for item in group_ids]
        if hwid_limit is not ...:
            kwargs["hwid_limit"] = hwid_limit
        if kwargs:
            panel.update_settings(**kwargs)
    return settings if isinstance(settings, dict) else {}


@dataclass
class Services:
    config: Config
    store: SettingsStore
    panels: dict[str, MarzbanClient]

    def panel(self, key: str) -> MarzbanClient:
        return self.panels[key]


def _services(context: ContextTypes.DEFAULT_TYPE) -> Services:
    return context.application.bot_data["services"]


async def _authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id in _services(context).config.admin_ids:
        return True
    if update.effective_message:
        await update.effective_message.reply_text("دسترسی ندارید.")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _authorized(update, context):
        return
    await update.effective_message.reply_text(
        "مدیریت ساخت گروهی کانفیگ مرزبان آماده است.",
        reply_markup=main_keyboard(),
    )


async def connection_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _authorized(update, context):
        return
    try:
        services = _services(context)
        alien = await services.panel("alien").get_inbounds()
        easy_status = []
        for panel_key in sorted(key for key in services.panels if key in EASY_PANEL_KEYS):
            await services.panel(panel_key).authenticate()
            easy_status.append(PANEL_LABELS.get(panel_key, panel_key))
        total = sum(len(items) for items in alien.values())
        protocols = "، ".join(name.upper() for name in sorted(alien)) or "هیچ‌کدام"
        await update.effective_message.reply_text(
            "✅ اتصال پنل‌ها برقرار است.\n\n"
            f"Alien: {protocols} | {total} اینباند\n"
            f"Pasarguard: {', '.join(easy_status) or '-'}",
            reply_markup=main_keyboard(),
        )
    except MarzbanError as exc:
        await update.effective_message.reply_text(
            f"❌ اتصال به پنل ناموفق بود:\n{exc}",
            reply_markup=main_keyboard(),
        )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _authorized(update, context):
        return
    services = _services(context)
    await update.effective_message.reply_text(
        "پنلی که می‌خواهید تنظیم کنید را انتخاب کنید:",
        reply_markup=settings_panel_keyboard(_configured_panel_labels(services)),
    )


async def settings_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _authorized(update, context):
        return
    services = _services(context)
    panel_key = (query.data or "").split(":", 1)[1]
    if panel_key not in services.panels:
        await query.answer("پنل معتبر نیست.", show_alert=True)
        return
    if panel_key in EASY_PANEL_KEYS:
        settings_payload = await _apply_easy_panel_settings(services, panel_key)
        panel = services.panel(panel_key)
        group_ids = getattr(panel, "group_ids", settings_payload.get("group_ids", []))
        hwid_limit = getattr(panel, "hwid_limit", settings_payload.get("hwid_limit"))
        await query.edit_message_text(
            f"تنظیمات {PANEL_LABELS.get(panel_key, panel_key)}\n\n"
            f"گروه‌ها: {group_ids or '-'}\n"
            f"HWID: {hwid_limit if hwid_limit is not None else '-'}",
            reply_markup=easy_panel_settings_keyboard(panel_key),
        )
        return

    try:
        inbounds = await services.panel("alien").get_inbounds()
    except MarzbanError as exc:
        await query.edit_message_text(f"خطا در دریافت اینباندها:\n{exc}")
        return
    selected = await services.store.get("selected_inbounds", {})
    context.user_data["available_inbounds"] = inbounds
    context.user_data["selected_inbounds"] = selected
    await query.edit_message_text(
        "اینباندهای موردنظر را انتخاب کنید. فقط اینباندهای فعال پنل نمایش داده می‌شوند.",
        reply_markup=inbound_keyboard(inbounds, selected),
    )


async def settings_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _authorized(update, context):
        return
    services = _services(context)
    await query.edit_message_text(
        "پنلی که می‌خواهید تنظیم کنید را انتخاب کنید:",
        reply_markup=settings_panel_keyboard(_configured_panel_labels(services)),
    )


async def easy_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _authorized(update, context):
        return
    _, panel_key, field = (query.data or "").split(":", 2)
    if panel_key not in _services(context).panels or panel_key not in EASY_PANEL_KEYS:
        await query.answer("پنل معتبر نیست.", show_alert=True)
        return
    context.user_data["easy_settings_edit"] = {"panel": panel_key, "field": field}
    prompt = (
        "شناسه گروه‌ها را با کاما بفرستید. مثال: 1,2"
        if field == "groups"
        else "عدد HWID را بفرستید. برای حذف مقدار اختصاصی، - بفرستید."
    )
    await query.message.reply_text(prompt, reply_markup=cancel_keyboard())


async def easy_settings_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _authorized(update, context):
        return
    edit = context.user_data.get("easy_settings_edit")
    if not edit:
        return
    text = (update.effective_message.text or "").strip()
    if text == CANCEL:
        context.user_data.pop("easy_settings_edit", None)
        await update.effective_message.reply_text("لغو شد.", reply_markup=main_keyboard())
        return
    services = _services(context)
    panel_key = edit["panel"]
    field = edit["field"]
    settings_payload = await services.store.get(f"panel_settings:{panel_key}", {})
    settings_payload = settings_payload if isinstance(settings_payload, dict) else {}
    try:
        if field == "groups":
            group_ids = [int(item.strip()) for item in text.split(",") if item.strip()]
            if not group_ids:
                raise ValueError
            settings_payload["group_ids"] = group_ids
        elif field == "hwid":
            settings_payload["hwid_limit"] = None if text == "-" else int(text)
            if settings_payload["hwid_limit"] is not None and settings_payload["hwid_limit"] < 0:
                raise ValueError
        else:
            await update.effective_message.reply_text("تنظیم معتبر نیست.")
            return
    except ValueError:
        await update.effective_message.reply_text("مقدار معتبر نیست.")
        return
    await services.store.set(f"panel_settings:{panel_key}", settings_payload)
    await _apply_easy_panel_settings(services, panel_key)
    context.user_data.pop("easy_settings_edit", None)
    await update.effective_message.reply_text(
        f"✅ تنظیمات {PANEL_LABELS.get(panel_key, panel_key)} ذخیره شد.",
        reply_markup=main_keyboard(),
    )


async def inbound_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await _authorized(update, context):
        return
    parts = query.data.split(":", 2)
    action = parts[1]
    available = context.user_data.get("available_inbounds", {})
    selected = context.user_data.get("selected_inbounds", {})

    if action == "save":
        selected = {protocol: tags for protocol, tags in selected.items() if tags}
        if not selected:
            await query.answer("حداقل یک اینباند انتخاب کنید.", show_alert=True)
            return
        await _services(context).store.set("selected_inbounds", selected)
        await query.edit_message_text("✅ تنظیمات اینباندها ذخیره شد.")
        await query.message.reply_text("منوی اصلی", reply_markup=main_keyboard())
        return
    if action == "all":
        selected = {
            protocol: [entry["tag"] for entry in entries]
            for protocol, entries in available.items()
        }
    elif action == "none":
        selected = {}
    else:
        protocol, tag = action, parts[2]
        tags = set(selected.get(protocol, []))
        tags.symmetric_difference_update({tag})
        selected[protocol] = sorted(tags)
    context.user_data["selected_inbounds"] = selected
    await query.edit_message_reply_markup(reply_markup=inbound_keyboard(available, selected))


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _authorized(update, context):
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "پنل مقصد را انتخاب کنید:",
        reply_markup=panel_keyboard(),
    )
    context.user_data["create"] = {}
    return PANEL


async def create_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    panel_key = PANEL_BUTTONS.get(update.effective_message.text)
    if not panel_key or panel_key not in _services(context).panels:
        await update.effective_message.reply_text("یکی از پنل‌ها را انتخاب کنید.")
        return PANEL
    services = _services(context)
    context.user_data["create"]["panel"] = panel_key
    if panel_key in EASY_PANEL_KEYS:
        context.user_data["create"]["inbounds"] = {}
        await update.effective_message.reply_text(
            "نوع زمان‌بندی را انتخاب کنید:",
            reply_markup=mode_keyboard(),
        )
        return MODE

    selected = await services.store.get("selected_inbounds", {})
    try:
        available = await services.panel("alien").get_inbounds()
    except MarzbanError as exc:
        await update.effective_message.reply_text(
            f"دریافت اینباندهای فعال ممکن نبود:\n{exc}",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END
    live_tags = {
        protocol: {entry["tag"] for entry in entries}
        for protocol, entries in available.items()
    }
    selected = {
        protocol: [tag for tag in tags if tag in live_tags.get(protocol, set())]
        for protocol, tags in selected.items()
    }
    selected = {protocol: tags for protocol, tags in selected.items() if tags}
    await services.store.set("selected_inbounds", selected)
    if not selected:
        await update.effective_message.reply_text(
            "ابتدا از بخش تنظیمات حداقل یک اینباند را انتخاب کنید.",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END
    context.user_data["create"]["inbounds"] = selected
    await update.effective_message.reply_text(
        "نوع زمان‌بندی را انتخاب کنید:",
        reply_markup=mode_keyboard(),
    )
    return MODE


async def create_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    modes = {MODE_HOLD: "on_hold", MODE_DATE: "date", MODE_UNLIMITED: "unlimited"}
    mode = modes.get(update.effective_message.text)
    if not mode:
        await update.effective_message.reply_text("یکی از گزینه‌های روی کیبورد را انتخاب کنید.")
        return MODE
    context.user_data["create"]["mode"] = mode
    await update.effective_message.reply_text(
        "حجم هر کانفیگ را به گیگ وارد کنید. برای نامحدود عدد 0 را بفرستید.",
        reply_markup=cancel_keyboard(),
    )
    return VOLUME


async def create_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    try:
        volume = int(update.effective_message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("حجم باید عدد صحیح باشد.")
        return VOLUME
    if volume < 0:
        await update.effective_message.reply_text("حجم نمی‌تواند منفی باشد.")
        return VOLUME
    context.user_data["create"]["volume_gb"] = volume
    await update.effective_message.reply_text("مدت اعتبار را به روز وارد کنید.")
    return DAYS


async def create_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    try:
        days = int(update.effective_message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("مدت باید عدد صحیح باشد.")
        return DAYS
    if days <= 0:
        await update.effective_message.reply_text("مدت باید بیشتر از صفر باشد.")
        return DAYS
    context.user_data["create"]["duration_days"] = days
    draft = context.user_data["create"]
    if draft["panel"] in EASY_PANEL_KEYS:
        panel = _services(context).panel(draft["panel"])
        default_hwid = getattr(panel, "hwid_limit", None)
        default_label = default_hwid if default_hwid is not None else "پیش‌فرض خود پنل"
        await update.effective_message.reply_text(
            "محدودیت HWID این batch را وارد کنید.\n"
            f"پیش‌فرض فعلی: {default_label}\n\n"
            "اگر می‌خواهید همان پیش‌فرض استفاده شود، دکمه پیش‌فرض را بزنید.",
            reply_markup=default_or_cancel_keyboard(),
        )
        return HWID
    return await _ask_seed(update)


async def create_hwid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.effective_message.text or "").strip()
    if text == CANCEL:
        return await cancel(update, context)
    if text == USE_DEFAULT or text == "-":
        context.user_data["create"]["hwid_limit"] = None
        return await _ask_seed(update)
    try:
        value = int(text)
    except ValueError:
        await update.effective_message.reply_text("HWID باید عدد باشد یا دکمه پیش‌فرض را بزنید.")
        return HWID
    if value < 0:
        await update.effective_message.reply_text("HWID نمی‌تواند منفی باشد.")
        return HWID
    context.user_data["create"]["hwid_limit"] = value
    return await _ask_seed(update)


async def _ask_seed(update: Update):
    await update.effective_message.reply_text(
        "نام کانفیگ اول را بفرستید. نام باید با عدد تمام شود.\n"
        "مثال: `PhantomHubs_Vpn_1`\n\n"
        "خط تیره به‌صورت خودکار به زیرخط تبدیل می‌شود.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return SEED


async def create_seed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    context.user_data["create"]["seed"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("تعداد کانفیگ‌ها را وارد کنید؛ حداکثر 100 عدد.")
    return COUNT


async def create_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    try:
        count = int(update.effective_message.text.strip())
    except ValueError:
        await update.effective_message.reply_text("تعداد باید عدد صحیح باشد.")
        return COUNT
    if not 1 <= count <= 100:
        await update.effective_message.reply_text("تعداد باید بین 1 تا 100 باشد.")
        return COUNT
    draft = context.user_data["create"]
    try:
        names = build_sequence(draft["seed"], count)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return SEED
    draft["names"] = names
    mode_label = {
        "on_hold": "شروع از اولین اتصال",
        "date": "تاریخ‌دار",
        "unlimited": "زمان نامحدود",
    }.get(draft["mode"], draft["mode"])
    volume_label = "نامحدود" if draft["volume_gb"] == 0 else f"{draft['volume_gb']} گیگ"
    panel_label = PANEL_LABELS.get(draft["panel"], draft["panel"])
    protocols = (
        "، ".join(protocol.upper() for protocol in draft["inbounds"])
        if draft["panel"] == "alien"
        else "MultiLocation (پیش‌فرض پنل)"
    )
    hwid_value = draft.get("hwid_limit")
    hwid_label = (
        "پیش‌فرض پنل"
        if draft["panel"] in EASY_PANEL_KEYS and hwid_value is None
        else str(hwid_value or "-")
    )
    await update.effective_message.reply_text(
        "پیش‌نمایش ساخت:\n\n"
        f"پنل: {panel_label}\n"
        f"نام‌ها: `{names[0]}` تا `{names[-1]}`\n"
        f"تعداد: {len(names)}\n"
        f"حجم هرکدام: {volume_label}\n"
        f"مدت: {draft['duration_days']} روز\n"
        f"نوع: {mode_label}\n"
        f"HWID: {hwid_label}\n"
        f"پروتکل‌ها: {protocols}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=confirm_keyboard(),
    )
    return REVIEW


async def create_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    if update.effective_message.text != CONFIRM:
        await update.effective_message.reply_text("تایید یا لغو را انتخاب کنید.")
        return REVIEW

    draft = context.user_data["create"]
    progress = await update.effective_message.reply_text("در حال ساخت کانفیگ‌ها: 0٪")
    created: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    total = len(draft["names"])
    for index, username in enumerate(draft["names"], start=1):
        spec = CreateSpec(
            username=username,
            volume_gb=draft["volume_gb"],
            duration_days=draft["duration_days"],
            mode=draft["mode"],
            inbounds=draft["inbounds"],
            hwid_limit=draft.get("hwid_limit"),
        )
        try:
            panel = _services(context).panel(draft["panel"])
            user = await panel.create_user(spec)
            subscription_url = str(user.get("subscription_url", "")).strip()
            if not subscription_url:
                failed.append((username, "پنل لینک اشتراک برنگرداند."))
            else:
                created.append((username, subscription_url))
        except MarzbanError as exc:
            failed.append((username, str(exc)))
        if index == total or index % 5 == 0:
            await progress.edit_text(
                f"در حال ساخت کانفیگ‌ها: {index}/{total}\n"
                f"موفق: {len(created)} | ناموفق: {len(failed)}"
            )

    await progress.edit_text(
        f"ساخت تمام شد؛ در حال ارسال لینک‌ها: 0/{len(created)}"
    )
    for username, link in created:
        while True:
            try:
                await update.effective_message.reply_text(
                    f"✅ {username}\n{link}",
                )
                break
            except RetryAfter as exc:
                await asyncio.sleep(float(exc.retry_after) + 0.5)
        await asyncio.sleep(0.05)

    summary = f"ارسال تمام شد.\nموفق: {len(created)}\nناموفق: {len(failed)}"
    if failed:
        failure_lines = []
        for username, error in failed:
            failure_lines.append(f"❌ {username}: {error}")
        failure_text = "\n".join(failure_lines)
        summary = f"{summary}\n\n{failure_text[:3500]}"

    await progress.edit_text(
        f"ساخت و ارسال تمام شد.\nموفق: {len(created)} | ناموفق: {len(failed)}"
    )
    await update.effective_message.reply_text(
        summary,
        reply_markup=main_keyboard(),
    )
    context.user_data.pop("create", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("create", None)
    await update.effective_message.reply_text("عملیات لغو شد.", reply_markup=main_keyboard())
    return ConversationHandler.END


def build_application(services: Services) -> Application:
    application = Application.builder().token(services.config.bot_token).build()
    application.bot_data["services"] = services
    create_flow = ConversationHandler(
        entry_points=[
            CommandHandler("create", create_start),
            MessageHandler(filters.Regex(f"^{CREATE}$"), create_start),
        ],
        states={
            PANEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_panel)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_mode)],
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_volume)],
            DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_days)],
            HWID: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_hwid)],
            SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_seed)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_count)],
            REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", connection_status))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, easy_settings_value), group=1)
    application.add_handler(create_flow)
    application.add_handler(MessageHandler(filters.Regex(f"^{STATUS}$"), connection_status))
    application.add_handler(MessageHandler(filters.Regex(f"^{SETTINGS}$"), settings))
    application.add_handler(CallbackQueryHandler(settings_panel_callback, pattern=r"^settings_panel:"))
    application.add_handler(CallbackQueryHandler(settings_back_callback, pattern=r"^settings_back$"))
    application.add_handler(CallbackQueryHandler(easy_settings_callback, pattern=r"^easy_settings:"))
    application.add_handler(CallbackQueryHandler(inbound_toggle, pattern=r"^inbound:"))
    return application
