import logging

from telegram import BotCommand

from .bot import Services, build_application
from .config import Config
from .marzban import EasyPanelClient, MarzbanClient
from .storage import SettingsStore


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = SettingsStore(config.database_path)
    alien = MarzbanClient(
        config.marzban_url,
        config.marzban_username,
        config.marzban_password,
        verify_ssl=config.verify_ssl,
    )
    easy = EasyPanelClient(
        config.easy_panel_url,
        config.easy_panel_username,
        config.easy_panel_password,
        group_ids=config.easy_panel_group_ids,
        verify_ssl=config.verify_ssl,
    )
    panels = {"alien": alien, "easy": easy}
    application = build_application(Services(config, store, panels))

    async def post_init(_application):
        await store.initialize()
        inbounds = await alien.get_inbounds()
        await easy.authenticate()
        selected = await store.get("selected_inbounds", {})
        if not selected:
            await store.set(
                "selected_inbounds",
                {
                    protocol: [entry["tag"] for entry in entries]
                    for protocol, entries in inbounds.items()
                },
            )
        await _application.bot.set_my_commands(
            [
                BotCommand("start", "منوی اصلی"),
                BotCommand("create", "ساخت گروهی کانفیگ"),
                BotCommand("settings", "انتخاب پروتکل و اینباند"),
                BotCommand("status", "بررسی اتصال پنل"),
                BotCommand("cancel", "لغو عملیات جاری"),
            ]
        )

    async def post_shutdown(_application):
        for panel in panels.values():
            await panel.close()

    application.post_init = post_init
    application.post_shutdown = post_shutdown
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
