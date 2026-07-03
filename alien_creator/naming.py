from __future__ import annotations

import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
TRAILING_NUMBER_RE = re.compile(r"^(.*?)(\d+)$")


def build_sequence(seed: str, count: int) -> list[str]:
    seed = seed.strip()
    match = TRAILING_NUMBER_RE.fullmatch(seed)
    if not match:
        raise ValueError("نام باید در انتها عدد داشته باشد؛ مثال: PhantomExpress10GB-VIP1")
    prefix, raw_start = match.groups()
    start = int(raw_start)
    names = [f"{prefix}{number}" for number in range(start, start + count)]
    invalid = next((name for name in names if not USERNAME_RE.fullmatch(name)), None)
    if invalid:
        raise ValueError(
            f"نام «{invalid}» با قوانین پنل سازگار نیست؛ فقط حروف انگلیسی، عدد، _ و - مجاز است."
        )
    return names
