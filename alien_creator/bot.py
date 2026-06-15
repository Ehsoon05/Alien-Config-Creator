from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
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
    SETTINGS,
    STATUS,
    cancel_keyboard,
    confirm_keyboard,
    inbound_keyboard,
    main_keyboard,
    mode_keyboard,
)
from .marzban import CreateSpec, MarzbanClient, MarzbanError
from .naming import build_sequence
from .storage import SettingsStore

logger = logging.getLogger(__name__)

MODE, VOLUME, DAYS, SEED, COUNT, REVIEW = range(6)


@dataclass
class Services:
    config: Config
    store: SettingsStore
    marzban: MarzbanClient


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
        inbounds = await _services(context).marzban.get_inbounds()
        total = sum(len(items) for items in inbounds.values())
        protocols = "، ".join(name.upper() for name in sorted(inbounds)) or "هیچ‌کدام"
        await update.effective_message.reply_text(
            f"✅ اتصال به پنل برقرار است.\nپروتکل‌ها: {protocols}\nتعداد اینباند فعال: {total}",
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
    try:
        inbounds = await services.marzban.get_inbounds()
    except MarzbanError as exc:
        await update.effective_message.reply_text(f"خطا در دریافت اینباندها:\n{exc}")
        return
    selected = await services.store.get("selected_inbounds", {})
    context.user_data["available_inbounds"] = inbounds
    context.user_data["selected_inbounds"] = selected
    await update.effective_message.reply_text(
        "اینباندهای موردنظر را انتخاب کنید. فقط اینباندهای فعال پنل نمایش داده می‌شوند.",
        reply_markup=inbound_keyboard(inbounds, selected),
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
    selected = await _services(context).store.get("selected_inbounds", {})
    if not selected:
        await update.effective_message.reply_text(
            "ابتدا از بخش تنظیمات حداقل یک اینباند را انتخاب کنید.",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END
    context.user_data["create"] = {"inbounds": selected}
    await update.effective_message.reply_text(
        "نوع زمان‌بندی را انتخاب کنید:",
        reply_markup=mode_keyboard(),
    )
    return MODE


async def create_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.text == CANCEL:
        return await cancel(update, context)
    modes = {MODE_HOLD: "on_hold", MODE_DATE: "date"}
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
    mode_label = "شروع از اولین اتصال" if draft["mode"] == "on_hold" else "تاریخ‌دار"
    volume_label = "نامحدود" if draft["volume_gb"] == 0 else f"{draft['volume_gb']} گیگ"
    protocols = "، ".join(protocol.upper() for protocol in draft["inbounds"])
    await update.effective_message.reply_text(
        "پیش‌نمایش ساخت:\n\n"
        f"نام‌ها: `{names[0]}` تا `{names[-1]}`\n"
        f"تعداد: {len(names)}\n"
        f"حجم هرکدام: {volume_label}\n"
        f"مدت: {draft['duration_days']} روز\n"
        f"نوع: {mode_label}\n"
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
            note="Created by Alien Config Creator",
        )
        try:
            user = await _services(context).marzban.create_user(spec)
            created.append((username, user.get("subscription_url", "")))
        except MarzbanError as exc:
            failed.append((username, str(exc)))
        if index == total or index % 5 == 0:
            await progress.edit_text(
                f"در حال ساخت کانفیگ‌ها: {index}/{total}\n"
                f"موفق: {len(created)} | ناموفق: {len(failed)}"
            )

    output = io.StringIO()
    for username, link in created:
        output.write(f"{username}\n{link}\n\n")
    if failed:
        output.write("\n--- FAILED ---\n")
        for username, error in failed:
            output.write(f"{username}: {error}\n")
    document = io.BytesIO(output.getvalue().encode("utf-8"))
    document.name = f"{draft['names'][0]}-{draft['names'][-1]}.txt"
    await update.effective_message.reply_document(
        document=document,
        caption=f"ساخت تمام شد.\nموفق: {len(created)}\nناموفق: {len(failed)}",
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
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_mode)],
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_volume)],
            DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_days)],
            SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_seed)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_count)],
            REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", connection_status))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(create_flow)
    application.add_handler(MessageHandler(filters.Regex(f"^{STATUS}$"), connection_status))
    application.add_handler(MessageHandler(filters.Regex(f"^{SETTINGS}$"), settings))
    application.add_handler(CallbackQueryHandler(inbound_toggle, pattern=r"^inbound:"))
    return application
