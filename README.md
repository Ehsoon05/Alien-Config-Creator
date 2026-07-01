# Alien Config Creator

ربات خصوصی تلگرام برای ساخت تکی یا گروهی کاربران Marzban.

## قابلیت‌ها

- اتصال مستقیم به API مرزبان
- ساخت کانفیگ `on_hold` با شروع اعتبار از اولین اتصال
- ساخت کانفیگ تاریخ‌دار با شروع اعتبار از زمان ساخت
- حجم محدود یا نامحدود
- ساخت گروهی نام‌های ترتیبی، مانند `PhantomHubs_Vpn_1` تا `PhantomHubs_Vpn_30`
- انتخاب فقط پروتکل‌ها و اینباندهای فعال پنل
- انتخاب پنل مقصد: `Alien` یا `آسان پنل`
- ساخت آسان پنل روی گروه `MultiLocation` بدون نیاز به انتخاب اینباند
- تبدیل اختیاری خروجی‌ها به لینک اختصاصی Phantom Subscription Panel
- ارسال هر نام و لینک اشتراک در یک پیام جداگانه
- دسترسی محدود به شناسه‌های عددی ادمین
- سرویس و آپدیتر مستقل systemd

## دستورات

- `/start` منوی اصلی
- `/create` ساخت گروهی کانفیگ
- `/settings` انتخاب اینباندهای فعال
- `/status` بررسی اتصال به پنل
- `/cancel` لغو عملیات جاری

## اجرای محلی

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m alien_creator.main
```

اطلاعات حساس را در `.env` یا `/etc/alien-config-creator.env` قرار دهید و هرگز
آن‌ها را داخل GitHub کامیت نکنید.

برای ساخت لینک اختصاصی Phantom، این مقدارها را هم تنظیم کنید:

```env
SUBSCRIPTION_PUBLIC_BASE_URL=https://api.phantomhubs.shop
SUBSCRIPTION_PANEL_SYNC_URL=https://api.phantomhubs.shop/internal/configs
SUBSCRIPTION_PANEL_SYNC_TOKEN=...
```

## نام‌گذاری گروهی

مرزبان فقط حروف انگلیسی، عدد و زیرخط را برای username می‌پذیرد. ربات خط تیره را
به زیرخط تبدیل می‌کند. اگر نام اول `PhantomHubs-Vpn-1` و تعداد `30` باشد،
کاربران `PhantomHubs_Vpn_1` تا `PhantomHubs_Vpn_30` ساخته می‌شوند.
