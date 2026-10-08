"""예매처 URL 정규화.

인터파크 티켓은 자동 수집을 막아두었지만 놀티켓과 상품번호가 같으므로 놀티켓 URL로 바꿔 수집한다.
"""
import re

NOL_PRODUCT = "https://nol.yanolja.com/ticket/products/{pid}"

_PATTERNS = [
    re.compile(r"nol\.yanolja\.com/ticket/(?:places/\d+/)?products/(\d+)"),
    re.compile(r"world\.nol\.com/(?:\w+/)?ticket/(?:places/\d+/)?products/(\d+)"),
    re.compile(r"tickets\.interpark\.com/goods/(\d+)"),
    re.compile(r"ticket\.interpark\.com/.*?GoodsCode=(\d+)", re.I),
]


def product_id_from_url(url: str) -> str:
    for p in _PATTERNS:
        m = p.search(url)
        if m:
            return m.group(1)
    return ""


def normalize_url(url: str) -> str:
    """수집용 URL. 알려진 예매처면 놀티켓 상품 URL로, 아니면 그대로."""
    url = url.strip()
    pid = product_id_from_url(url)
    return NOL_PRODUCT.format(pid=pid) if pid else url
