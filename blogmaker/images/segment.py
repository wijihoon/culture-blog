"""긴 상세 이미지에서 사진 후보 구역 찾기.

방식: 재귀 XY-cut
  1) 한 줄(가로 또는 세로)이 거의 한 가지 색이면 '여백'으로 본다.
     배경, 얇은 구분선(빨간 가로/세로선)은 줄 전체가 단색이라 여백이 되고,
     사진·글자 줄은 줄 안에 색이 섞여 있어 '내용'이 된다.
  2) 여백을 기준으로 구역을 가로·세로로 번갈아 나눈다.
  3) 각 구역을 사진 / 글자 / 그래픽으로 분류한다.
좌표는 모두 원본 이미지 기준.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .. import config
from ..models import Candidate

ANALYSIS_W = 420     # 분석용 축소 너비
DEV_T = 10           # 줄 대표색(중앙값)과 이만큼 다르면 '다른 색' 픽셀 (어두운 무대 사진 대응)
ACTIVE_RATIO = 0.02  # 줄에서 다른 색 픽셀 비율이 이 이상이면 내용 줄
MIN_GAP = 3          # 이보다 얇은 여백은 무시 (분석 해상도 px)
THIN_RUN = 2         # 이보다 얇은 내용 줄 묶음은 잡음/구분선으로 무시
MAX_DEPTH = 6


def _line_activity(rgb: np.ndarray, axis: int) -> np.ndarray:
    """axis=0: 가로줄별, axis=1: 세로줄별 '다른 색 픽셀' 비율."""
    lum = rgb.mean(axis=2)
    if axis == 0:
        med = np.median(lum, axis=1, keepdims=True)
    else:
        med = np.median(lum, axis=0, keepdims=True)
    dev = np.abs(lum - med) > DEV_T
    # 색상 차이도 반영 (같은 밝기의 빨강/검정 구분)
    for c in range(3):
        ch = rgb[..., c]
        m = np.median(ch, axis=1, keepdims=True) if axis == 0 else np.median(ch, axis=0, keepdims=True)
        dev |= np.abs(ch - m) > DEV_T * 2
    return dev.mean(axis=1 if axis == 0 else 0)


def _runs(active: np.ndarray) -> list[tuple[int, int]]:
    runs, n, i = [], len(active), 0
    while i < n:
        if active[i]:
            j = i
            while j < n and active[j]:
                j += 1
            if j - i > THIN_RUN:
                runs.append([i, j])
            i = j
        else:
            i += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < MIN_GAP:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [tuple(r) for r in merged]


def _xycut(rgb, x0, y0, x1, y1, axis, depth, stuck, out, min_w, min_h):
    sub = rgb[y0:y1, x0:x1]
    if sub.size == 0 or depth > MAX_DEPTH:
        out.append((x0, y0, x1, y1))
        return
    runs = _runs(_line_activity(sub, axis) > ACTIVE_RATIO)
    if axis == 0:
        parts = [(x0, y0 + a, x1, y0 + b) for a, b in runs]
    else:
        parts = [(x0 + a, y0, x0 + b, y1) for a, b in runs]
    if not parts:
        return
    if len(parts) == 1:
        p = parts[0]
        if stuck:                      # 두 방향 모두 더 안 나뉨 → 확정
            out.append(p)
            return
        _xycut(rgb, *p, 1 - axis, depth + 1, True, out, min_w, min_h)
        return
    for p in parts:
        if (p[2] - p[0]) < min_w or (p[3] - p[1]) < min_h:
            continue
        _xycut(rgb, *p, 1 - axis, depth + 1, False, out, min_w, min_h)


def _color_entropy(rgb: np.ndarray) -> float:
    q = (rgb // 32).astype(np.int32)
    codes = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    hist = np.bincount(codes.ravel(), minlength=512).astype(float)
    p = hist[hist > 0] / hist.sum()
    return float(-(p * np.log2(p)).sum())


def _classify(rgb: np.ndarray) -> tuple[str, float]:
    """photo: 중간 밝기 픽셀이 충분하고 색이 다양 / text: 단색 배경 위 글자 / 그 외 graphic(약도·로고·리뷰 카드)."""
    ent = _color_entropy(rgb)
    gray = rgb.mean(axis=2)
    mid = float(((gray > 45) & (gray < 215)).mean())
    if ent >= 2.7 and mid >= 0.15:
        return "photo", ent
    if mid < 0.13 and ent < 2.2:
        return "text", ent
    return "graphic", ent


def find_candidates(img: Image.Image) -> list[Candidate]:
    img = img.convert("RGB")
    W, H = img.size
    scale = ANALYSIS_W / W if W > ANALYSIS_W else 1.0
    small = img.resize((max(1, int(W * scale)), max(1, int(H * scale))), Image.BILINEAR)
    arr = np.asarray(small).astype(np.int16)
    sw, sh = small.size
    min_w = int(sw * config.MIN_CANDIDATE_W_RATIO)
    min_h = int(config.MIN_CANDIDATE_H_PX * scale)

    raw: list[tuple[int, int, int, int]] = []
    _xycut(arr, 0, 0, sw, sh, 0, 0, False, raw, min_w, min_h)

    cands = []
    for (x0, y0, x1, y1) in raw:
        if (x1 - x0) < min_w or (y1 - y0) < min_h:
            continue
        box = (int(x0 / scale), int(y0 / scale), min(W, int(round(x1 / scale))), min(H, int(round(y1 / scale))))
        kind, score = _classify(np.asarray(img.crop(box))[::2, ::2].astype(np.int16))
        cands.append((box, kind, score))

    cands.sort(key=lambda c: (c[0][1], c[0][0]))
    cands = cands[: config.MAX_CANDIDATES]
    return [Candidate(id=f"C{i + 1:02d}", box=b, kind=k, score=round(s, 2)) for i, (b, k, s) in enumerate(cands)]
