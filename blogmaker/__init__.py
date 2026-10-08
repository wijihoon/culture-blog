"""blogmaker: 예매 링크 + 상세 이미지 zip → 네이버 블로그 초안 HTML.

패키지 구성
  sources/   예매처 페이지 수집·파싱 (놀티켓, 인터파크 링크 변환)
  images/    zip 풀기, 사진 후보 구역 분할, 자르기
  writers/   글 작성 (Claude API 우선, 실패 시 규칙 기반)
  render/    게시글·홈·업로드 화면 HTML 생성
  pipeline   요청 폴더 처리 흐름
"""
__version__ = "1.0.0"
