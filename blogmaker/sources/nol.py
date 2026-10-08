"""놀티켓 상품 페이지 수집·파싱.

페이지는 서버 렌더링된 텍스트에 '장소/기간/시간/연령' 라벨, 좌석별 가격, 공지사항이 들어 있다.
HTML 구조(클래스명)는 자주 바뀌므로 화면 텍스트 기준으로 파싱한다.
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from .. import config
from ..models import ShowInfo, PriceRow
from .url import normalize_url, product_id_from_url

GENRES = ["뮤지컬", "연극", "콘서트", "클래식", "오페라", "무용", "국악", "전시", "아동", "가족",
          "넌버벌", "퍼포먼스", "서커스", "마술", "행사", "축제"]

SECTION_HEADS = {"공지사항", "상품 상세", "상품상세", "가격", "할인정보", "이용안내", "취소 및 환불 규정",
                 "장소", "리뷰", "적립 및 결제 혜택", "오픈예정 안내", "예매 안내사항", "캐스팅", "출연진"}


def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": config.USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"},
                     timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text


def fetch_show_info(url: str) -> tuple[ShowInfo, list[str]]:
    """(수집 정보, 상세 이미지 URL 목록)"""
    target = normalize_url(url)
    html = fetch_html(target)
    info, detail_images = parse_show_info(html, source_url=url)
    return info, detail_images


def _lines(soup: BeautifulSoup) -> list[str]:
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text("\n")
    out = []
    for ln in text.splitlines():
        ln = re.sub(r"[ \t ​]+", " ", ln).strip()
        if ln:
            out.append(ln)
    return out


def _after_label(lines: list[str], label: str) -> str:
    for i, ln in enumerate(lines[:-1]):
        if ln == label:
            return lines[i + 1]
    return ""


def _sections(lines: list[str], head: str, limit: int = 80) -> list[list[str]]:
    """제목 줄이 나오는 모든 위치에서, 다음 섹션 제목 전까지의 본문들."""
    found = []
    for i, ln in enumerate(lines):
        if ln == head:
            body = []
            for x in lines[i + 1:i + 1 + limit]:
                if x in SECTION_HEADS:
                    break
                body.append(x)
            if body:
                found.append(body)
    return found


def _section(lines: list[str], head: str, limit: int = 80) -> list[str]:
    s = _sections(lines, head, limit)
    return s[0] if s else []


def _meta(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return (tag.get("content") or "").strip() if tag else ""


def parse_show_info(html: str, source_url: str = "") -> tuple[ShowInfo, list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    # 이미지 (script 제거 전에)
    detail_images = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if "/Play/image/etc/" in src and src not in detail_images:
            detail_images.append(src.replace("http://", "https://"))
    poster = _meta(soup, "og:image")
    keywords = [k.strip() for k in _meta(soup, "keywords").split(",") if k.strip()]
    og_title = _meta(soup, "og:title")

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        title = re.sub(r"\s*\S*\s*일정 및 예매\s*\|.*$", "", og_title).strip()

    lines = _lines(soup)

    genre = ""
    for k in keywords[1:3]:
        if any(g in k for g in GENRES):
            genre = k
            break
    if not genre:
        m = re.search(r"(\S+) 일정 및 예매", og_title)
        genre = m.group(1) if m else ""

    venue = _after_label(lines, "장소")
    period = _after_label(lines, "기간")
    running = _after_label(lines, "시간")
    age = _after_label(lines, "연령")

    # 가격: '가격' 섹션의 [좌석명, 금액] 쌍
    prices = []
    price_lines = _section(lines, "가격", 40)
    for a, b in zip(price_lines, price_lines[1:]):
        if re.fullmatch(r"[\d,]+원", b) and len(a) <= 20 and not re.search(r"\d+원", a):
            prices.append(PriceRow(seat=a, price=b))

    # 티켓 오픈, 회차
    ticket_open = ""
    schedule = ""
    for ln in lines:
        m = re.search(r"티켓\s*오픈\s*(?:안내)?\s*[:：]\s*(.+)", ln)
        if m and not ticket_open:
            ticket_open = m.group(1).strip()
    run = _section(lines, "운영 시간", 4)
    if run:
        schedule = run[0]
    if not schedule:
        for i, ln in enumerate(lines):
            m = re.search(r"공연\s*기간\s*[:：]\s*(.+)", ln)
            if m:
                parts = [m.group(1).strip()]
                if i + 1 < len(lines) and re.match(r"^\d{1,2}월\s*\d{1,2}일", lines[i + 1]):
                    parts.append(lines[i + 1])
                schedule = " / ".join(parts)
                break

    # 기획사·문의
    organizer, contact = "", ""
    for ln in lines:
        m = re.search(r"(기획사|주최|주관)\s*[:：]\s*([^)\n,]+)", ln)
        if m and not organizer:
            organizer = m.group(2).strip()
        if not contact and "문의" in ln:
            p = re.search(r"\d{2,4}-\d{3,4}-\d{4}", ln)
            if p:
                contact = ln.strip()

    # 공지사항
    notices = []
    for ln in _section(lines, "공지사항", 120):
        if re.fullmatch(r"[-=*\s]*[^-=]{1,15}[-=\s]*", ln) and ln.strip().endswith("-"):
            continue                      # '- 관람 안내 -' 같은 소제목
        t = ln.lstrip("*-•· ").strip()
        if len(t) >= 6:
            notices.append(t)

    # 장소 섹션 주소 ('장소'는 상단 라벨에도 있으므로 모든 위치 확인)
    address = ""
    for body in _sections(lines, "장소", 6):
        for ln in body:
            if re.search(r"(시|도)\s?\S*(구|군)\s?\S*(동|로|길)\s*\d", ln):
                address = ln
                break
        if address:
            break

    info = ShowInfo(
        source_url=source_url or "",
        product_id=product_id_from_url(source_url) if source_url else "",
        title=title, genre=genre, venue=venue, address=address, period=period,
        running_time=running, age=age, schedule=schedule, ticket_open=ticket_open,
        prices=prices, organizer=organizer, contact=contact, notices=notices[:40],
        poster_url=poster, page_text="\n".join(lines)[:8000],
    )
    return info, detail_images
