"""تبدیل تاریخ میلادی به شمسی برای نمایش؛ تاریخ ذخیره‌شده همچنان ISO میلادی است."""
from datetime import date

_GREGORIAN_MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

def gregorian_to_jalali(value: date) -> tuple[int, int, int]:
    gy, gm, gd = value.year, value.month, value.day
    gy2 = gy - 1600
    jy = 979
    day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    day_no += gd + _GREGORIAN_MONTH_START[gm - 1]
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        day_no += 1
    day_no -= 79
    jy += 33 * (day_no // 12053)
    day_no %= 12053
    jy += 4 * (day_no // 1461)
    day_no %= 1461
    if day_no > 365:
        jy += (day_no - 1) // 365
        day_no = (day_no - 1) % 365
    if day_no < 186:
        jm, jd = 1 + day_no // 31, 1 + day_no % 31
    else:
        jm, jd = 7 + (day_no - 186) // 30, 1 + (day_no - 186) % 30
    return jy, jm, jd

def format_jalali_date(value: date | str, *, persian_digits: bool = True) -> str:
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    y, m, d = gregorian_to_jalali(value)
    rendered = f"{y:04d}/{m:02d}/{d:02d}"
    return rendered.translate(_PERSIAN_DIGITS) if persian_digits else rendered

def sort_by_gregorian_date(records: list[dict], key: str = "sale_date") -> list[dict]:
    return sorted(records, key=lambda item: date.fromisoformat(str(item[key])[:10]) if item.get(key) else date.min)
