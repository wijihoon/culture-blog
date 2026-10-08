"""정적 사이트 생성: 홈(목록), 업로드 화면, 게시글 페이지."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import config
from ..models import Post
from .post import format_period, info_rows, line_html, seller_name, slot_text

HERE = Path(__file__).parent


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(HERE / "templates"),
                      autoescape=select_autoescape(["html", "j2"]), trim_blocks=False, lstrip_blocks=False)
    env.globals.update(line_html=line_html, slot_text=slot_text)
    return env


def short_title(post: Post) -> str:
    m = re.search(r"<([^>]+)>", post.draft.blog_title)
    if m:
        return m.group(1)
    t = re.sub(r"^\d{4}\s*", "", post.info.title)
    return re.sub(r"\s*-\s*\S+$", "", t).strip() or post.info.title or post.id


def render_post(env: Environment, post: Post) -> str:
    return env.get_template("post.html.j2").render(
        post=post, d=post.draft, rows=info_rows(post.info),
        seller=seller_name(post.info.source_url), short_title=short_title(post))


def load_posts(content_dir: Path) -> tuple[list[Post], list[dict]]:
    posts, failed = [], []
    if not content_dir.exists():
        return posts, failed
    for d in sorted(content_dir.iterdir()):
        if (d / "post.json").exists():
            posts.append(Post.model_validate_json((d / "post.json").read_text(encoding="utf-8")))
        elif (d / "error.json").exists():
            failed.append(json.loads((d / "error.json").read_text(encoding="utf-8")))
    posts.sort(key=lambda p: p.created_at, reverse=True)
    return posts, failed


def build_site(out_dir: Path, content_dir: Path = config.CONTENT_DIR) -> int:
    env = _env()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "posts").mkdir(parents=True)
    shutil.copytree(HERE / "static", out_dir / "assets")
    (out_dir / ".nojekyll").write_text("")

    posts, failed = load_posts(content_dir)
    summary = []
    for p in posts:
        src = content_dir / p.id
        dst = out_dir / "posts" / p.id
        dst.mkdir(parents=True)
        if (src / "img").exists():
            shutil.copytree(src / "img", dst / "img")
        if (src / "images.zip").exists():
            shutil.copy2(src / "images.zip", dst / "images.zip")
        (dst / "index.html").write_text(render_post(env, p), encoding="utf-8")
        thumb_num = p.image_map.get(p.draft.hero_image_id or "", 1)
        thumb = next((im.file for im in p.images if im.num == thumb_num), p.images[0].file if p.images else "")
        summary.append({"id": p.id, "title": short_title(p), "full_title": p.info.title, "genre": p.info.genre,
                        "venue": p.info.venue, "period": format_period(p.info.period), "mode": p.mode,
                        "created_at": p.created_at, "thumb": thumb})

    repo = os.environ.get("GITHUB_REPOSITORY", "/")
    owner, _, name = repo.partition("/")
    (out_dir / "index.html").write_text(
        env.get_template("index.html.j2").render(posts=summary, failed=failed, site_title=config.SITE_TITLE),
        encoding="utf-8")
    (out_dir / "upload.html").write_text(
        env.get_template("upload.html.j2").render(site_title=config.SITE_TITLE, owner=owner, repo=name),
        encoding="utf-8")
    (out_dir / "posts.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(posts)
