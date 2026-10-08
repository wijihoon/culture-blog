"""상세 이미지 처리: zip 풀기 → 후보 구역 찾기 → 자르기."""
from .archive import load_detail_image
from .segment import find_candidates
from .crop import crop_candidates, contact_sheet, tiles_for_vision

__all__ = ["load_detail_image", "find_candidates", "crop_candidates", "contact_sheet", "tiles_for_vision"]
