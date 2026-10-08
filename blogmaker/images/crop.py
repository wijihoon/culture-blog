"""후보 구역 자르기, Claude에게 보여줄 후보 목록 시트와 원본 타일 만들기."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..models import Candidate

KIND_COLOR = {"photo": (0, 200, 90), "graphic": (255, 170, 0), "text": (0, 140, 255)}


def _font(size: int):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def crop_candidates(img: Image.Image, cands: list[Candidate], ids: list[str], out_dir: Path,
                    names: dict[str, str]) -> dict[str, Path]:
    """선택된 후보만 잘라 저장. names: 후보ID → 파일명(확장자 제외)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {c.id: c for c in cands}
    saved = {}
    for cid in ids:
        c = by_id.get(cid)
        if not c:
            continue
        path = out_dir / f"{names[cid]}.jpg"
        img.crop(c.box).save(path, quality=90, optimize=True)
        saved[cid] = path
    return saved


def contact_sheet(img: Image.Image, cands: list[Candidate], cell: int = 300, cols: int = 5) -> Image.Image:
    """후보 구역 썸네일을 번호와 함께 한 장에 모은 시트."""
    font = _font(22)
    rows = (len(cands) + cols - 1) // cols or 1
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 34)), "white")
    d = ImageDraw.Draw(sheet)
    for i, c in enumerate(cands):
        th = img.crop(c.box)
        th.thumbnail((cell - 10, cell - 10))
        x, y = (i % cols) * cell, (i // cols) * (cell + 34)
        sheet.paste(th, (x + (cell - th.width) // 2, y + 32 + (cell - 10 - th.height) // 2))
        w, h = c.box[2] - c.box[0], c.box[3] - c.box[1]
        d.text((x + 6, y + 4), f"{c.id}  {w}x{h}", fill=KIND_COLOR.get(c.kind, (0, 0, 0)), font=font)
    return sheet


def tiles_for_vision(img: Image.Image, cands: list[Candidate], max_tiles: int = 8,
                     tile_h_ratio: float = 2.4) -> list[Image.Image]:
    """원본을 위에서부터 타일로 나누고 후보 박스와 ID를 그려 넣는다 (글자·문맥 파악용)."""
    W, H = img.size
    tile_h = int(W * tile_h_ratio)
    n = min(max_tiles, (H + tile_h - 1) // tile_h)
    if n * tile_h < H:          # 타일 수 제한 시 타일 높이를 늘림
        tile_h = (H + n - 1) // n
    font = _font(max(18, W // 30))
    tiles = []
    for t in range(n):
        y0, y1 = t * tile_h, min(H, (t + 1) * tile_h)
        tile = img.crop((0, y0, W, y1)).copy()
        d = ImageDraw.Draw(tile)
        for c in cands:
            if c.box[3] <= y0 or c.box[1] >= y1:
                continue
            bx = (c.box[0], c.box[1] - y0, c.box[2], c.box[3] - y0)
            d.rectangle(bx, outline=(255, 0, 255), width=max(3, W // 200))
            d.rectangle((bx[0], max(0, bx[1]), bx[0] + font.size * 2.6, max(0, bx[1]) + font.size + 8), fill=(255, 0, 255))
            d.text((bx[0] + 4, max(0, bx[1]) + 2), c.id, fill="white", font=font)
        if tile.height > 2000 or tile.width > 2000:
            tile.thumbnail((2000, 2000))
        tiles.append(tile)
    return tiles
