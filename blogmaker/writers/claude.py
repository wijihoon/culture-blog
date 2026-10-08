"""Claude API 작성기: 상세 이미지 타일 + 후보 시트 + 수집 정보로 PostDraft 생성."""
from __future__ import annotations

import base64
import io
import json

from PIL import Image

from .. import config
from ..images import contact_sheet, tiles_for_vision
from ..models import Candidate, PostDraft, ShowInfo
from .prompts import SYSTEM, user_text


class ClaudeUnavailable(RuntimeError):
    """API 키 없음·잔액 부족·호출 실패 등 → 규칙 작성기로 대체."""


def _image_block(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.b64encode(buf.getvalue()).decode()}}


def write(info: ShowInfo, img: Image.Image, cands: list[Candidate]) -> PostDraft:
    if not config.ANTHROPIC_API_KEY:
        raise ClaudeUnavailable("ANTHROPIC_API_KEY 가 설정되지 않음")
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise ClaudeUnavailable(f"anthropic 패키지 없음: {e}")

    W = img.width
    tiles = tiles_for_vision(img, cands)
    sheet = contact_sheet(img, cands)
    content: list[dict] = []
    for i, t in enumerate(tiles, 1):
        content.append({"type": "text", "text": f"상세 이미지 타일 {i}/{len(tiles)}:"})
        content.append(_image_block(t))
    content.append({"type": "text", "text": "후보 목록 시트:"})
    content.append(_image_block(sheet))

    cand_desc = "\n".join(
        f"{c.id}: 위치 y={c.box[1]}~{c.box[3]}, 크기 {c.box[2]-c.box[0]}x{c.box[3]-c.box[1]} "
        f"(원본 너비 {W}), 자동분류={c.kind}" for c in cands)
    info_json = json.dumps(info.model_dump(exclude={"page_text"}), ensure_ascii=False, indent=1)
    content.append({"type": "text", "text": user_text(info_json, info.page_text[:5000], cand_desc, len(tiles))})

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2, timeout=300)
    try:
        resp = client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_format=PostDraft,
        )
    except anthropic.APIStatusError as e:      # 401(키 오류), 402/400(잔액 부족) 등
        raise ClaudeUnavailable(f"Claude API 오류 {e.status_code}: {getattr(e, 'message', e)}")
    except anthropic.APIError as e:
        raise ClaudeUnavailable(f"Claude API 호출 실패: {e}")

    if resp.stop_reason in ("refusal", "max_tokens") or resp.parsed_output is None:
        raise ClaudeUnavailable(f"Claude 응답을 사용할 수 없음 (stop_reason={resp.stop_reason})")
    return resp.parsed_output
