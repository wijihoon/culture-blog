"""요청 하나를 게시글로 만드는 전체 흐름.

requests/<요청ID>/request.json  {"url": "...", "created_at": "..."}
requests/<요청ID>/<아무이름>.zip  상세 이미지 (없으면 예매 페이지의 상세 이미지를 내려받아 시도)
        ↓
content/posts/<요청ID>/post.json, img/NN_*.jpg, images.zip
"""
from __future__ import annotations

import io
import json
import logging
import re
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from PIL import Image

from . import config
from .images import crop_candidates, find_candidates, load_detail_image
from .images.archive import stack_vertical
from .models import Candidate, Post, PostDraft, PostImage, ShowInfo
from .sources import fetch_show_info, normalize_url, product_id_from_url
from .writers import write_draft

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


def _download_images(urls: list[str]) -> Image.Image | None:
    imgs = []
    for u in urls[:6]:
        try:
            r = requests.get(u, headers={"User-Agent": config.USER_AGENT}, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content))
            im.load()
            imgs.append(im.convert("RGB"))
        except Exception as e:  # noqa: BLE001
            log.warning("상세 이미지 다운로드 실패 %s: %s", u, e)
    return stack_vertical(imgs) if imgs else None


def _clean_draft(draft: PostDraft, cands: list[Candidate]) -> tuple[PostDraft, list[str]]:
    """존재하지 않거나 중복된 후보 ID 제거, 사용 순서대로 ID 목록 반환."""
    valid = {c.id for c in cands}
    used: list[str] = []

    def take(cid):
        if cid and cid in valid and cid not in used:
            used.append(cid)
            return cid
        return None

    draft.hero_image_id = take(draft.hero_image_id)
    draft.intro_image_id = take(draft.intro_image_id)
    for g in draft.recommend:
        g.image_ids = [x for x in (take(i) for i in g.image_ids) if x]
    if draft.highlights:
        for it in draft.highlights.items:
            it.image_ids = [x for x in (take(i) for i in it.image_ids) if x]
        draft.highlights.items = [it for it in draft.highlights.items if it.image_ids or it.title]
    draft.map_image_id = take(draft.map_image_id)
    draft.tags = [t if t.startswith("#") else f"#{t}" for t in (re.sub(r"\s+", "", t) for t in draft.tags) if t.strip("#")]
    return draft, used


def _slug(label: str, cid: str) -> str:
    ascii_ = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return ascii_ or cid.lower()


def build_post(post_id: str, url: str, detail: Image.Image | None, info: ShowInfo | None,
               out_root: Path, created_at: str | None = None, draft: PostDraft | None = None) -> Post:
    """draft를 주면 작성기 대신 그 초안을 사용 (대화에서 직접 다듬은 글 등록용, mode='manual')."""
    warnings: list[str] = []
    if info is None:
        info = ShowInfo(source_url=url, product_id=product_id_from_url(url))
        warnings.append("예매 페이지 정보를 가져오지 못해 일부 항목이 비어 있습니다")
    if detail is None:
        raise ValueError("상세 이미지가 없습니다 (zip을 함께 올려주세요)")

    cands = find_candidates(detail)
    if draft is not None:
        mode = "manual"
    else:
        draft, mode, w = write_draft(info, detail, cands)
        warnings += w
    draft, used = _clean_draft(draft, cands)

    labels = {l.id: l.label for l in draft.image_labels}
    post_dir = out_root / post_id
    if post_dir.exists():
        shutil.rmtree(post_dir)
    img_dir = post_dir / "img"
    names = {cid: f"{n:02d}_{_slug('', cid)}" for n, cid in enumerate(used, 1)}
    saved = crop_candidates(detail, cands, used, img_dir, names)

    images = [PostImage(num=n, file=f"img/{saved[cid].name}", label=labels.get(cid, "사진"))
              for n, cid in enumerate(used, 1) if cid in saved]
    with zipfile.ZipFile(post_dir / "images.zip", "w", zipfile.ZIP_STORED) as zf:
        for im in images:
            zf.write(post_dir / im.file, arcname=Path(im.file).name)

    post = Post(
        id=post_id,
        created_at=created_at or datetime.now(KST).isoformat(timespec="seconds"),
        mode=mode,
        model=config.CLAUDE_MODEL if mode == "claude" else "",
        info=info,
        draft=draft,
        images=images,
        image_map={cid: n for n, cid in enumerate(used, 1)},
        warnings=warnings,
    )
    (post_dir / "post.json").write_text(post.model_dump_json(indent=1), encoding="utf-8")
    return post


def process_request(req_dir: Path, out_root: Path) -> Post:
    meta = json.loads((req_dir / "request.json").read_text(encoding="utf-8"))
    url = meta["url"].strip()
    log.info("요청 처리: %s (%s)", req_dir.name, url)

    info, detail_urls = None, []
    try:
        info, detail_urls = fetch_show_info(normalize_url(url))
        info.source_url = url
    except Exception as e:  # noqa: BLE001
        log.warning("예매 페이지 수집 실패: %s", e)

    files = [p for p in req_dir.iterdir() if p.name != "request.json" and not p.name.startswith(".")]
    detail = None
    for f in files:
        try:
            detail = load_detail_image(f)
            break
        except Exception as e:  # noqa: BLE001
            log.warning("업로드 파일 읽기 실패 %s: %s", f.name, e)
    if detail is None and detail_urls:
        detail = _download_images(detail_urls)

    return build_post(req_dir.name, url, detail, info, out_root, meta.get("created_at"))


def process_all(requests_dir: Path = config.REQUESTS_DIR, out_root: Path = config.CONTENT_DIR) -> list[str]:
    """대기 중인 요청을 모두 처리. 성공한 요청 폴더는 삭제, 실패하면 error.txt를 남기고 둔다."""
    done = []
    if not requests_dir.exists():
        return done
    for req in sorted(p for p in requests_dir.iterdir() if p.is_dir()):
        if not (req / "request.json").exists() or (req / "error.txt").exists():
            continue
        try:
            post = process_request(req, out_root)
            shutil.rmtree(req)
            done.append(post.id)
            log.info("완료: %s (%s)", post.id, post.mode)
        except Exception as e:  # noqa: BLE001
            log.exception("요청 실패: %s", req.name)
            (req / "error.txt").write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
            err_dir = out_root / req.name
            err_dir.mkdir(parents=True, exist_ok=True)
            (err_dir / "error.json").write_text(json.dumps({"id": req.name, "error": str(e)}, ensure_ascii=False),
                                                encoding="utf-8")
    return done
