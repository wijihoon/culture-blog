"""규칙 기반 작성기 (Claude API를 쓸 수 없을 때).

수집 정보만으로 사실 위주의 문장을 만들고, 사진은 크기·위치·분류로 자동 배치한다.
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image

from ..models import (Candidate, Highlights, HighlightItem, ImageLabel, Line, PostDraft,
                      RecommendGroup, ShowInfo)

KEYWORDS_BY_GENRE = [
    (("넌버벌", "퍼포먼스"), ["대사 한마디 없이~", "몸짓과 액션", "그리고 웃음", "온 가족이 함께!"]),
    (("뮤지컬",), ["노래와 이야기", "그리고 무대", "그리고 감동!"]),
    (("연극",), ["배우의 숨결이", "가까이 닿는", "연극 무대!"]),
    (("콘서트", "공연"), ["라이브의 힘~", "그리고 무대", "그리고 환호!"]),
    (("클래식", "오페라"), ["깊은 울림~", "그리고 선율", "그리고 여운!"]),
    (("전시",), ["눈으로 걷는 시간~", "작품", "그리고 이야기!"]),
]


def _short_title(title: str) -> str:
    t = re.sub(r"^\d{4}\s*", "", title)
    t = re.sub(r"\s*-\s*\S+$", "", t)       # '- 울산' 같은 지역 꼬리
    return t.strip() or title


def _region(title: str, venue: str) -> str:
    m = re.search(r"-\s*(\S+)$", title)
    if m:
        return m.group(1)
    return venue[:2] if venue else ""


def _first_date(period: str) -> str:
    m = re.search(r"\d{4}\.(\d{1,2})\.(\d{1,2})", period)
    return f"{int(m.group(1)):02d}{int(m.group(2)):02d}" if m else ""


def _white_ratio(img: Image.Image, box) -> float:
    a = np.asarray(img.crop(box))[::3, ::3].astype(np.int16)
    return float((a.min(axis=2) > 225).mean())


def _pick_images(img: Image.Image, cands: list[Candidate]):
    W, H = img.size
    def tall_card(c):   # 글자 많은 세로형 카드(리뷰 등)
        return c.kind == "graphic" and (c.box[3] - c.box[1]) > (c.box[2] - c.box[0]) * 1.1 and c.box[1] > H * 0.15
    usable = [c for c in cands if (c.kind == "photo" or (c.kind == "graphic" and c.score >= 2.0)) and not tall_card(c)]
    # 상단의 작은 로고 구역 제외
    usable = [c for c in usable if not (c.box[1] < H * 0.08 and (c.box[2] - c.box[0]) < W * 0.9 and c.kind != "photo")]
    map_c = None
    for c in reversed(cands):
        if c.box[1] > H * 0.7 and _white_ratio(img, c.box) > 0.45:
            map_c = c
            break
    usable = [c for c in usable if c is not map_c]
    hero = None
    for c in usable:
        w, h = c.box[2] - c.box[0], c.box[3] - c.box[1]
        if c.box[1] < H * 0.25 and h > w * 0.9:
            hero = c
            break
    rest = [c for c in usable if c is not hero]
    large = [c for c in rest if (c.box[2] - c.box[0]) >= W * 0.55]
    small = [c for c in rest if (c.box[2] - c.box[0]) < W * 0.55]
    return hero, large, small, map_c


def write(info: ShowInfo, img: Image.Image, cands: list[Candidate]) -> PostDraft:
    hero, large, small, map_c = _pick_images(img, cands)
    name = _short_title(info.title)
    region = _region(info.title, info.venue)
    genre = info.genre or "공연"
    is_exhibit = "전시" in genre
    mmdd = _first_date(info.period)

    kw = next((k for keys, k in KEYWORDS_BY_GENRE if any(x in info.title + genre for x in keys)),
              ["놓치면 아쉬운~", "이번 시즌", "추천 공연!"])

    intro = [Line(text=f"{genre}<{name}>", style="accent"),
             Line(text=f"{info.venue}에서 만나는 무대." if info.venue else "이번 시즌 무대.", style="normal")]
    if info.period:
        intro.append(Line(text=f"{info.period}", style="bold"))
    if info.running_time:
        intro.append(Line(text=f"러닝타임 {info.running_time}", style="normal"))

    groups: list[RecommendGroup] = []
    li = iter(large)
    if info.age:
        groups.append(RecommendGroup(lines=[Line(text=f"관람 연령은 {info.age.replace('관람가능', '').replace('관람가', '').strip()}", style="normal"),
                                            Line(text="가족 나들이 일정으로 체크!", style="accent")],
                                     image_ids=[c.id for c in [next(li, None)] if c]))
    if info.running_time:
        groups.append(RecommendGroup(lines=[Line(text=f"러닝타임 {info.running_time}", style="normal"),
                                            Line(text="부담 없이 즐기기 좋은 길이~", style="accent")],
                                     image_ids=[c.id for c in [next(li, None)] if c]))
    if info.schedule or info.period:
        groups.append(RecommendGroup(lines=[Line(text="공연 일정은 짧게!", style="normal"),
                                            Line(text="예매는 서두르기를.", style="accent")],
                                     image_ids=[c.id for c in [next(li, None)] if c]))

    remaining = list(li)
    items: list[HighlightItem] = []
    for c in remaining:
        items.append(HighlightItem(subtitle="", title="", image_ids=[c.id]))
    for i in range(0, len(small), 2):
        items.append(HighlightItem(subtitle="", title="", image_ids=[c.id for c in small[i:i + 2]]))
    highlights = Highlights(section_title="현장 미리보기", lead="사진으로 먼저 만나보기~", items=items) if items else None

    tips: list[Line] = []
    for n in info.notices:
        if not any(k in n for k in ("관람가", "1인 1티켓", "입장", "수령", "주차", "대중교통", "시야", "불편", "반입")):
            continue
        t = re.sub(r"\s+", " ", n).strip()
        # 긴 문장은 쉼표 기준으로 두 줄 (원글처럼 한 줄 한 호흡)
        head, sep, tail = t.partition(", ")
        if sep and len(t) > 30:
            tips += [Line(text=head + ",", style="normal"), Line(text=tail, style="normal")]
        else:
            tips += [Line(text=t, style="normal"), Line(text="", style="small")]
        if len(tips) >= 8:
            break
    tips = [l for l in tips if l.text]

    venue_search = re.sub(r"\s*(대공연장|소공연장|중공연장|대극장|소극장|중극장|\S*홀|\S*관)$", "", info.venue).strip() or info.venue
    tag_name = re.sub(r"\s+", "", name)
    tags = [f"#{tag_name}", f"#{genre}{tag_name}", f"#{re.sub(r'\s+', '', info.venue)}" if info.venue else "",
            f"#{region}{genre}" if region else "", f"#{region}공연" if region else "", "#공연추천", "#공연정보",
            f"#{tag_name}예매"]
    tags = [t for t in tags if t and t != "#"]

    labels = []
    for c in ([hero] if hero else []) + large + small + ([map_c] if map_c else []):
        w = c.box[2] - c.box[0]
        labels.append(ImageLabel(id=c.id, label="대표 비주얼" if c is hero else ("약도" if c is map_c else
                                 ("장면 사진" if w >= img.width * 0.55 else "인물 사진"))))

    head = f"~{mmdd}전시정보" if is_exhibit else f"{mmdd}공연정보"
    title = f"■[{head}]{genre}<{name}>{region}_{info.venue}" if mmdd else f"■{genre}<{name}>{region}_{info.venue}"

    return PostDraft(
        blog_title=title,
        keywords=kw,
        hero_image_id=hero.id if hero else None,
        intro=intro,
        intro_note="",
        intro_image_id=None,
        recommend=groups,
        reviews=[],
        highlights=highlights,
        tips=tips,
        venue_search=venue_search,
        map_image_id=map_c.id if map_c else None,
        closing=["이번 기회에 꼭 보기를~"],
        tags=tags,
        image_labels=labels,
    )
