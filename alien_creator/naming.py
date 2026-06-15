from __future__ import annotations

import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
TRAILING_NUMBER_RE = re.compile(r"^(.*?)(\d+)$")


def build_sequence(seed: str, count: int) -> list[str]:
    seed = seed.strip().replace("-", "_")
    match = TRAILING_NUMBER_RE.fullmatch(seed)
    if not match:
        raise ValueError("نام باید در انتها عدد داشته باشد؛ مثال: PhantomHubs_Vpn_1")
    prefix, raw_start = match.groups()
    start = int(raw_start)
    names = [f"{prefix}{number}" for number in range(start, start + count)]
    invalid = next((name for name in names if not USERNAME_RE.fullmatch(name)), None)
    if invalid:
        raise ValueError(
            f"نام «{invalid}» با قوانین مرزبان سازگار نیست؛ فقط حروف انگلیسی، عدد و _ مجاز است."
        )
    return names

