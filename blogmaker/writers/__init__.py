"""글 작성기 선택: Claude 우선, 사용 불가 시 규칙 기반."""
from __future__ import annotations

import logging

from PIL import Image

from .. import config
from ..models import Candidate, PostDraft, ShowInfo
from . import claude, rules

log = logging.getLogger(__name__)


def write_draft(info: ShowInfo, img: Image.Image, cands: list[Candidate]) -> tuple[PostDraft, str, list[str]]:
    """(초안, 모드, 경고 목록)"""
    warnings: list[str] = []
    try:
        draft = claude.write(info, img, cands)
        return draft, "claude", warnings
    except claude.ClaudeUnavailable as e:
        msg = f"Claude 작성기 사용 불가 → 규칙 작성기로 대체: {e}"
        log.warning(msg)
        warnings.append(msg)
    return rules.write(info, img, cands), "rules", warnings


__all__ = ["write_draft"]
