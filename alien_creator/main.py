import logging

from .bot import Services, build_application
from .config import Config
from .marzban import MarzbanClient
from .storage import SettingsStore


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    store = SettingsStore(config.database_path)
    marzban = MarzbanClient(
        config.marzban_url,
        config.marzban_username,
        config.marzban_password,
        verify_ssl=config.verify_ssl,
    )
    application = build_application(Services(config, store, marzban))

    async def post_init(_application):
        await store.initialize()
        inbounds = await marzban.get_inbounds()
        selected = await store.get("selected_inbounds", {})
        if not selected:
            await store.set(
                "selected_inbounds",
                {
                    protocol: [entry["tag"] for entry in entries]
                    for protocol, entries in inbounds.items()
                },
            )

    async def post_shutdown(_application):
        await marzban.close()

    application.post_init = post_init
    application.post_shutdown = post_shutdown
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

