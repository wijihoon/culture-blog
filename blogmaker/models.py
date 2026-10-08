"""게시글 데이터 모델.

- ShowInfo: 예매 페이지에서 수집한 사실 정보 (작성기가 바꾸지 않음)
- Candidate: 상세 이미지에서 찾아낸 사진 후보 구역
- PostDraft: 작성기(Claude 또는 규칙)가 만드는 글 구성
- Post: 렌더링·저장 단위 (content/posts/<id>/post.json)
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------- 수집 정보 ----------

class PriceRow(BaseModel):
    seat: str
    price: str


class ShowInfo(BaseModel):
    source_url: str
    product_id: str = ""
    title: str = ""                 # 상품명 그대로
    genre: str = ""                 # 뮤지컬, 연극, 콘서트, 전시 ...
    venue: str = ""
    address: str = ""
    period: str = ""                # 2026.12.12 ~ 2026.12.13
    running_time: str = ""          # 80분
    age: str = ""                   # 36개월이상 관람가
    schedule: str = ""              # 공연 회차 안내
    ticket_open: str = ""
    prices: list[PriceRow] = Field(default_factory=list)
    organizer: str = ""             # 기획사
    contact: str = ""               # 문의
    notices: list[str] = Field(default_factory=list)   # 공지사항 문장
    poster_url: str = ""
    page_text: str = ""             # 작성기 참고용 본문 텍스트 (잘라서 사용)


# ---------- 이미지 후보 ----------

class Candidate(BaseModel):
    id: str                          # C01, C02 ...
    box: tuple[int, int, int, int]   # x0, y0, x1, y1 (상세 이미지 원본 좌표)
    kind: str                        # photo / text / graphic
    score: float = 0.0               # 사진다움 점수


# ---------- 작성기 출력 (Claude 구조화 출력 스키마로도 사용) ----------

class Line(BaseModel):
    text: str = Field(description="한 줄 문장. 가운데 정렬로 한 줄씩 쌓인다. 15~25자 내외")
    style: str = Field(description="normal | bold | accent(빨강 굵게 강조) | purple(보라 설명) | small(회색 작은 글씨)")


class RecommendGroup(BaseModel):
    lines: list[Line]
    image_ids: list[str] = Field(description="이 묶음 뒤에 넣을 사진 후보 ID (0~2개)")


class Review(BaseModel):
    text: str = Field(description="리뷰 핵심을 한국어로 짧게 의역 (원문 그대로 길게 인용 금지)")
    source: str = Field(description="매체명")


class HighlightItem(BaseModel):
    subtitle: str = Field(description="보라색 작은 설명 한 줄. 예: '1.무술 가족 집에 찾아온 손님'")
    title: str = Field(description="보라색 굵은 제목. 예: '특별한 손님의 정체는?'")
    image_ids: list[str] = Field(description="이 항목 뒤에 넣을 사진 후보 ID (0~3개). 2장은 나란히 배치됨")


class Highlights(BaseModel):
    section_title: str = Field(description="예: 에피소드 미리보기 / 캐릭터 소개 / 전시 구성")
    lead: str = Field(description="구역 첫 줄. 예: '무술 가족에게 무슨 일이?'")
    items: list[HighlightItem]


class ImageLabel(BaseModel):
    id: str
    label: str = Field(description="사진 설명 (예: 점프 장면, 무대 단체 사진)")


class PostDraft(BaseModel):
    blog_title: str = Field(description="■[MMDD공연정보]{장르}<{작품명}>{지역}_{키워드}_{키워드}_{공연장} 형식")
    keywords: list[str] = Field(description="장르 키워드 3~4줄. 첫 줄은 빨강, 나머지는 굵게+기울임")
    hero_image_id: Optional[str] = Field(description="키워드 아래 대표 비주얼 사진 후보 ID")
    intro: list[Line] = Field(description="작품 소개 5~9줄. 확인된 사실만")
    intro_note: str = Field(description="출처 표기 한 줄 (예: '(공연 이력·관객 수는 제작사 소개 기준)'), 없으면 빈 문자열")
    intro_image_id: Optional[str]
    recommend: list[RecommendGroup] = Field(description="추천 포인트 2~4묶음. 각 묶음 3~4줄, 마지막 줄은 accent")
    reviews: list[Review] = Field(description="상세 이미지에 실린 리뷰가 있을 때만. 없으면 빈 배열")
    highlights: Optional[Highlights]
    tips: list[Line] = Field(description="관람 전 체크 4~8줄 (공지사항 기반)")
    venue_search: str = Field(description="네이버 지도 '장소' 검색에 바로 걸리는 공식 명칭 (홀 이름 제외)")
    map_image_id: Optional[str] = Field(description="상세 이미지의 약도/오시는 길 구역 ID, 없으면 null")
    closing: list[str] = Field(description="맺음말 1~2줄")
    tags: list[str] = Field(description="#포함 태그 10~14개")
    image_labels: list[ImageLabel] = Field(description="사용한 모든 사진 후보 ID의 설명")


# ---------- 저장 단위 ----------

class PostImage(BaseModel):
    num: int
    file: str          # img/01_scene.jpg
    label: str


class Post(BaseModel):
    id: str
    created_at: str
    mode: str                      # claude / rules
    model: str = ""
    info: ShowInfo
    draft: PostDraft
    images: list[PostImage] = Field(default_factory=list)
    image_map: dict[str, int] = Field(default_factory=dict)   # 후보 ID → 사진 번호
    warnings: list[str] = Field(default_factory=list)
