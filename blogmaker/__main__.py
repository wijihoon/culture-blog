"""명령줄 진입점.

  python -m blogmaker process              requests/ 의 대기 요청을 모두 처리
  python -m blogmaker site --out _site     content/ 로 정적 사이트 생성
  python -m blogmaker local --url URL --zip FILE [--html 저장된페이지.html] [--id ID] [--draft 초안.json]
                                           요청 폴더 없이 한 건 바로 만들기 (로컬 테스트용)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="blogmaker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("process")
    s = sub.add_parser("site")
    s.add_argument("--out", default="_site")
    l = sub.add_parser("local")
    l.add_argument("--url", required=True)
    l.add_argument("--zip", required=True)
    l.add_argument("--html", help="예매 페이지를 미리 저장한 HTML (네트워크 없이 테스트)")
    l.add_argument("--id")
    l.add_argument("--draft", help="작성기 대신 사용할 PostDraft JSON (직접 다듬은 글 등록)")
    l.add_argument("--created-at")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "process":
        from .pipeline import process_all
        done = process_all()
        print(f"처리 완료 {len(done)}건: {', '.join(done) or '-'}")
        return 0

    if args.cmd == "site":
        from .render import build_site
        n = build_site(Path(args.out))
        print(f"사이트 생성: 게시글 {n}편 → {args.out}")
        return 0

    if args.cmd == "local":
        from .images import load_detail_image
        from .pipeline import build_post, KST
        from .sources import fetch_show_info, parse_show_info
        from datetime import datetime
        if args.html:
            info, _ = parse_show_info(Path(args.html).read_text(encoding="utf-8"), source_url=args.url)
        else:
            info, _ = fetch_show_info(args.url)
            info.source_url = args.url
        pid = args.id or datetime.now(KST).strftime("%Y%m%d-%H%M%S") + "-" + (info.product_id or "x")
        draft = None
        if args.draft:
            from .models import PostDraft
            draft = PostDraft.model_validate_json(Path(args.draft).read_text(encoding="utf-8"))
        post = build_post(pid, args.url, load_detail_image(args.zip), info, config.CONTENT_DIR,
                          created_at=args.created_at, draft=draft)
        print(f"생성: content/posts/{post.id} (작성 방식: {post.mode}, 사진 {len(post.images)}장)")
        for w in post.warnings:
            print("경고:", w)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
