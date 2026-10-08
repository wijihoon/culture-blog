"""업로드된 zip에서 상세 이미지를 꺼낸다.

- macOS 압축 부산물(__MACOSX, ._ 파일)은 무시
- 이미지가 여러 장이면(상세 이미지가 -01, -02로 나뉜 경우) 파일명 순서대로 세로로 이어 붙인다
- zip 대신 이미지 파일 하나를 올려도 동작
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None   # 세로로 매우 긴 상세 이미지 허용

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UNZIPPED = 200 * 1024 * 1024


def _images_from_zip(path: Path) -> list[tuple[str, Image.Image]]:
    out = []
    with zipfile.ZipFile(path) as zf:
        total = sum(i.file_size for i in zf.infolist())
        if total > MAX_UNZIPPED:
            raise ValueError("압축을 푼 크기가 너무 큽니다 (200MB 초과)")
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            name = info.filename
            base = name.rsplit("/", 1)[-1]
            if info.is_dir() or "__MACOSX" in name or base.startswith("._"):
                continue
            if Path(base).suffix.lower() not in IMAGE_EXT:
                continue
            img = Image.open(io.BytesIO(zf.read(info)))
            img.load()
            out.append((base, img.convert("RGB")))
    return out


def stack_vertical(images: list[Image.Image]) -> Image.Image:
    width = max(im.width for im in images)
    resized = [im if im.width == width else im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
               for im in images]
    canvas = Image.new("RGB", (width, sum(im.height for im in resized)), "white")
    y = 0
    for im in resized:
        canvas.paste(im, (0, y))
        y += im.height
    return canvas


def load_detail_image(path: str | Path) -> Image.Image:
    path = Path(path)
    if path.suffix.lower() == ".zip":
        items = _images_from_zip(path)
    elif path.suffix.lower() in IMAGE_EXT:
        img = Image.open(path)
        img.load()
        items = [(path.name, img.convert("RGB"))]
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {path.name}")
    if not items:
        raise ValueError("zip 안에 이미지 파일이 없습니다")
    if len(items) == 1:
        return items[0][1]
    return stack_vertical([im for _, im in items])
