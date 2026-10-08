"""파이프라인 테스트 (네트워크·API 키 없이 실행).

  python -m pytest -q
"""
from __future__ import annotations

import json
import types
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from blogmaker import config
from blogmaker.images import find_candidates, load_detail_image
from blogmaker.models import PostDraft
from blogmaker.pipeline import build_post, process_all
from blogmaker.render import build_site
from blogmaker.sources import normalize_url, parse_show_info
from blogmaker.writers import claude as claude_writer

FIX = Path(__file__).parent / "fixtures"
URL = "https://nol.yanolja.com/ticket/products/26014046"


def make_detail(path: Path) -> Path:
    """검정 배경에 '사진'(노이즈) 4장과 글자 줄, 빨간 구분선이 있는 가짜 상세 이미지."""
    rng = np.random.default_rng(0)
    W, H = 840, 3000
    img = Image.new("RGB", (W, H), "black")
    d = ImageDraw.Draw(img)
    photos = [(0, 100, 840, 600), (0, 900, 840, 1300), (560, 1500, 800, 1800), (560, 1850, 800, 2150)]
    for (x0, y0, x1, y1) in photos:
        noise = rng.integers(40, 220, size=(y1 - y0, x1 - x0, 3), dtype=np.uint8)
        img.paste(Image.fromarray(noise), (x0, y0))
    for y in range(1520, 1700, 30):                      # 왼쪽 글자 줄
        d.rectangle((40, y, 480, y + 10), fill="white")
    d.rectangle((520, 1450, 523, 2200), fill=(220, 30, 40))   # 세로 구분선
    d.rectangle((0, 1440, 840, 1443), fill=(220, 30, 40))     # 가로 구분선
    p = path / "detail.jpg"
    img.save(p, quality=92)
    z = path / "detail.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(p, "26014046-01.jpg")
        zf.writestr("__MACOSX/._26014046-01.jpg", b"junk")
    return z


@pytest.fixture
def info():
    i, _ = parse_show_info((FIX / "nol_26014046.html").read_text(encoding="utf-8"), URL)
    return i


def test_parse(info):
    assert info.venue == "울산문화예술회관 대공연장"
    assert info.period == "2026.12.12 ~ 2026.12.13"
    assert info.running_time == "80분"
    assert [(p.seat, p.price) for p in info.prices] == [("R석", "66,000원"), ("S석", "44,000원")]
    assert info.address == "울산시 남구 달동 413-13"
    assert info.organizer == "좋은날음악기획"
    assert not any(n.endswith("-") for n in info.notices)


def test_url():
    assert normalize_url("https://tickets.interpark.com/goods/26014046") == URL


def test_segment_finds_photos(tmp_path):
    img = load_detail_image(make_detail(tmp_path))
    boxes = [c.box for c in find_candidates(img) if c.kind == "photo"]
    # 큰 사진 2장 + 구분선 너머 작은 사진 2장이 각각 분리되어야 함
    assert len(boxes) == 4, boxes
    assert any(b[0] >= 540 and b[3] - b[1] > 250 for b in boxes)


def test_rules_mode(tmp_path, info, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    post = build_post("t1", URL, load_detail_image(make_detail(tmp_path)), info, tmp_path / "out")
    assert post.mode == "rules" and post.images
    assert (tmp_path / "out/t1/images.zip").exists()


def test_claude_mode_mocked(tmp_path, info, monkeypatch):
    """Claude 응답을 흉내 내어 ID 정리·번호 매기기·렌더링까지 확인."""
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    draft = PostDraft.model_validate_json((FIX / "jump_draft.json").read_text(encoding="utf-8"))
    draft.hero_image_id = "C01"
    draft.intro_image_id = "C01"        # 중복 → 제거되어야 함
    draft.map_image_id = "C99"          # 없는 ID → 제거되어야 함
    for it in draft.highlights.items:
        it.image_ids = ["C03", "C04"]   # 중복 사용 → 첫 항목만 남음

    class FakeMessages:
        def parse(self, **kw):
            assert kw["model"] == config.CLAUDE_MODEL
            return types.SimpleNamespace(parsed_output=draft, stop_reason="end_turn")

    class FakeClient:
        def __init__(self, **kw):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    post = build_post("t2", URL, load_detail_image(make_detail(tmp_path)), info, tmp_path / "out")
    assert post.mode == "claude"
    assert post.draft.intro_image_id is None and post.draft.map_image_id is None
    nums = sorted(post.image_map.values())
    assert nums == list(range(1, len(nums) + 1))
    n = build_site(tmp_path / "site", tmp_path / "out")
    html = (tmp_path / "site/posts/t2/index.html").read_text(encoding="utf-8")
    assert n == 1 and "[사진 01 넣기" in html and "울산문화예술회관" in html


def test_claude_failure_falls_back(tmp_path, info, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "bad-key")
    import anthropic

    class FakeMessages:
        def parse(self, **kw):
            err = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
            err.status_code, err.message = 401, "invalid x-api-key"
            raise err

    class FakeClient:
        def __init__(self, **kw):
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    post = build_post("t3", URL, load_detail_image(make_detail(tmp_path)), info, tmp_path / "out")
    assert post.mode == "rules"
    assert any("401" in w for w in post.warnings)


def test_process_all(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    from blogmaker import pipeline
    page = (FIX / "nol_26014046.html").read_text(encoding="utf-8")
    monkeypatch.setattr(pipeline, "fetch_show_info", lambda url: parse_show_info(page, url))
    req = tmp_path / "requests" / "20261008-000000-26014046"
    req.mkdir(parents=True)
    (req / "request.json").write_text(json.dumps({"url": URL}), encoding="utf-8")
    make_detail(req)
    (req / "detail.jpg").unlink()
    done = process_all(tmp_path / "requests", tmp_path / "out")
    assert done == ["20261008-000000-26014046"]
    assert not req.exists()
    assert (tmp_path / "out" / done[0] / "post.json").exists()
