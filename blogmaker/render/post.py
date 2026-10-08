"""게시글 페이지 렌더링 (네이버 블로그 붙여넣기용 초안 화면)."""
from __future__ import annotations

import re
from datetime import date
from html import escape

from markupsafe import Markup

from ..models import Post, ShowInfo

WEEK = "월화수목금토일"
STYLE = {
    "normal": "color:#000000;font-size:11pt;",
    "bold": "color:#000000;font-size:11pt;font-weight:bold;",
    "accent": "color:#ff0010;font-size:11pt;font-weight:bold;",
    "purple": "color:#bc61ab;font-size:11pt;",
    "small": "color:#888888;font-size:9pt;",
}


def line_html(text: str, style: str) -> Markup:
    css = STYLE.get(style, STYLE["normal"])
    t = escape(text)
    if "font-weight:bold" in css:
        t = f"<b>{t}</b>"
    return Markup(f'<span style="{css.replace("font-weight:bold;", "")}">{t}</span>')


def _with_weekday(s: str) -> str:
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", s.strip())
    if not m:
        return s.strip()
    y, mo, d = map(int, m.groups())
    try:
        wd = WEEK[date(y, mo, d).weekday()]
    except ValueError:
        return s.strip()
    return f"{y}.{mo:02d}.{d:02d}({wd})"


def format_period(period: str) -> str:
    parts = [p.strip() for p in re.split(r"~", period) if p.strip()]
    if len(parts) == 2:
        a, b = _with_weekday(parts[0]), _with_weekday(parts[1])
        if a[:5] == b[:5]:            # 같은 해면 뒤쪽 연도 생략
            b = b[5:]
        return f"{a} ~ {b}"
    return _with_weekday(period) if period else ""


def format_schedule(s: str) -> str:
    s = re.sub(r"^\s*공연\s*[:：]\s*", "", s)
    s = re.sub(r"(\d{1,2})시", r"\1:00", s)
    s = s.replace("요일", "").replace(", ", " · ")
    return "<br>".join(escape(p.strip()) for p in re.split(r"[/]", s) if p.strip())


def seller_name(url: str) -> str:
    if "interpark" in url:
        return "인터파크 티켓"
    if "yes24" in url:
        return "예스24 티켓"
    if "melon" in url:
        return "멜론티켓"
    if "nol" in url or "yanolja" in url:
        return "NOL 티켓"
    return "예매처"


def info_rows(info: ShowInfo) -> list[tuple[str, Markup]]:
    rows: list[tuple[str, str]] = []
    if info.title:
        rows.append(("🎭 공연명", f"<b>{escape(info.title)}</b>"))
    if info.genre:
        rows.append(("🎬 장르", escape(info.genre)))
    if info.period:
        rows.append(("📅 기간", f'<b style="color:#ff0010;">{escape(format_period(info.period))}</b>'))
    if info.schedule:
        rows.append(("🕒 공연시간", format_schedule(info.schedule)))
    if info.venue:
        rows.append(("📍 장소", escape(info.venue)))
    if info.running_time:
        rows.append(("⏱ 러닝타임", escape(info.running_time)))
    if info.age:
        age = re.sub(r"\s*관람\s*가능?$", "", info.age).replace("이상", " 이상").replace("  ", " ")
        extra = ' <span style="color:#888;">(1인 1티켓)</span>' if any("1인 1티켓" in n for n in info.notices) else ""
        rows.append(("👶 관람연령", escape(age) + extra))
    if info.prices:
        rows.append(("💰 가격", "<br>".join(f"{escape(p.seat)} <b>{escape(p.price)}</b>" for p in info.prices)))
    if info.ticket_open:
        rows.append(("🎟 티켓오픈", escape(info.ticket_open)))
    rows.append(("🛒 예매처", seller_name(info.source_url)))
    if info.organizer or info.contact:
        phone = re.search(r"\d{2,4}-\d{3,4}-\d{4}", info.contact or "")
        val = escape(info.organizer)
        if phone:
            val += f'<br><span style="color:#888;">문의 {phone.group(0)}</span>'
        rows.append(("🏢 기획사", val))
    return [(a, Markup(b)) for a, b in rows]


def slot_text(post: Post, ids: list[str]) -> Markup | None:
    """[사진 NN 넣기 · 설명] 자리표시."""
    nums = [post.image_map[i] for i in ids if i in post.image_map]
    if not nums:
        return None
    label = next((im.label for im in post.images if im.num == nums[0]), "사진")
    tag = " + ".join(f"{n:02d}" for n in nums)
    hint = " · 2장 나란히" if len(nums) == 2 else (f" · {len(nums)}장" if len(nums) > 2 else "")
    return Markup(f"[사진 {escape(tag)} 넣기 · {escape(label)}{hint}]")
