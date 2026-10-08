"""환경 설정 (GitHub Actions의 Secret/Variable로 덮어쓸 수 있음)."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("BLOGMAKER_ROOT", Path(__file__).resolve().parent.parent))
REQUESTS_DIR = ROOT / "requests"
CONTENT_DIR = ROOT / "content" / "posts"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-sonnet-5-5"

HTTP_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# 사진 후보: 너무 작은 구역은 버림 (상세 이미지 너비 대비 비율)
MIN_CANDIDATE_W_RATIO = 0.18
MIN_CANDIDATE_H_PX = 120
MAX_CANDIDATES = 40

SITE_TITLE = "공연·전시 블로그 초안"
