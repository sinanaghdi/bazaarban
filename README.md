# بازاربان | تحلیل فروش، مشتریان و عملکرد کسب‌وکارهای کوچک

بازاربان یک نمونه‌کار فارسی و راست‌چین (RTL) برای نمایش مهارت‌های تحلیل داده است. این پروژه آموزشی است، نه نرم‌افزار حسابداری و نه مدرک تقاضای بازار.

> تمام داده‌ها مصنوعی‌اند. فروشگاه‌ها، کالاها، فاکتورها و مشتریان ساختگی هستند؛ هیچ نتیجه‌ای در این مخزن بیانگر عملکرد کسب‌وکار واقعی، سود واقعی یا تقاضای بازار ایران نیست.

## قابلیت‌ها
- تولید قطعی دادهٔ مصنوعی با seed ثابت و manifest؛
- ممیزی کیفیت بدون حذف خاموش ردیف‌های مشکوک؛
- محاسبهٔ فروش، فاکتور یکتا، کالا، فروشگاه و مشتری تکراری با Python و Pandas؛
- تعریف KPI با فرمول و مخرج روشن؛
- SQL آموزشی سازگار با SQLite و تست تطبیق SQL/Pandas روی fixture؛
- داشبورد فارسی RTL با فیلتر تاریخ و فروشگاه؛
- ذخیرهٔ تاریخ به قالب ISO میلادی و نمایش شمسی در رابط کاربری.

## راه‌اندازی در Windows / PowerShell
پیش‌نیاز: Python 3.11 یا جدیدتر. از ریشهٔ مخزن اجرا کنید:

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python scripts/generate_demo_data.py
    python -m pytest -q
    python scripts/run_analysis.py
    python -m http.server 8000

سپس http://localhost:8000/dashboard/ را باز کنید. داشبورد برای خواندن JSON به وب‌سرور محلی نیاز دارد؛ بازکردن مستقیم HTML با file:// کار نمی‌کند. فایل‌های CSV/JSON تولیدی در Git ثبت نشده‌اند و با اسکریپت generator بازتولید می‌شوند. GitHub Actions نیز تولید داده، تست و تحلیل را اجرا می‌کند.

## تعریف KPIها و محدودیت‌ها
فاکتور از شناسهٔ distinct شمرده می‌شود، نه تعداد ردیف. «فروش خالص مثبت» معادل درآمد حسابداری یا سود نیست؛ هزینه، مالیات، موجودی و تسویه در داده وجود ندارد. مقدار quantity منفی نیز صرفاً نمونه‌ای مصنوعی برای تمرین کنترل کیفیت است. برای جزئیات، به docs/kpi_dictionary.md و docs/data_dictionary.md رجوع کنید.

## ساختار پروژه
- src/bazaarban/analytics.py: ingestion، ممیزی کیفیت و KPIها؛
- src/bazaarban/generator.py: تولید دادهٔ مصنوعی؛
- src/bazaarban/calendar_fa.py: تبدیل تاریخ برای نمایش؛
- dashboard/: رابط تعاملی RTL؛
- sql/: schema و پرس‌وجوهای SQLite؛
- tests/: تست محاسبات، تاریخ و سازگاری SQL/Pandas؛
- docs/: فرهنگ داده، تعریف شاخص‌ها و روش‌شناسی؛
- reports/management_report_fa.md: قالب گزارش مدیریتی فارسی.

## اعتبارسنجی با دیتاست عمومی واقعی

موتور تحلیل و قراردادهای KPI روی [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) با **541,909 ردیف** در [GitHub Actions](https://github.com/sinanaghdi/bazaarban/actions/runs/39745670035) اجرا شده‌اند؛ کنترل تعداد ردیف، حفظ ردیف‌ها، تطبیق Python با محاسبات مستقل و آشتی SQL/SQLite با Pandas موفق بوده است. گزارش عددها، QA، تعاریف و محدودیت‌های adapter در [docs/uci_online_retail_benchmark.md](docs/uci_online_retail_benchmark.md) است. ۱۳ تست Python نیز در [اجرای CI](https://github.com/sinanaghdi/bazaarban/actions/runs/39745670158) موفق شده‌اند.

این benchmark از adapter جداگانه استفاده می‌کند؛ **داشبورد دمو همچنان از دیتاست مصنوعی استفاده می‌کند**. UCI Online Retail فقط یک کسب‌وکار آنلاین را توصیف می‌کند، ستون شعبه، تخفیف و دسته‌بندی ندارد و مبلغ‌ها به GBP هستند. صفر گذاشتن تخفیف برای تطبیق schema فقط فرض adapter است، نه دادهٔ واقعی منبع. این نسخه backend، احراز هویت، PostgreSQL یا فایل Power BI ندارد. برای استفادهٔ تجاری به داده و مجوز و تعریف مالی تأییدشده نیاز است.
