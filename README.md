# culture-blog

예매 링크와 상세 이미지 zip을 올리면 **네이버 블로그에 붙여넣을 공연·전시 소개글 초안**을 만들어 GitHub Pages에 게시합니다.

- 홈: 만든 초안 목록
- 새 글 만들기: 링크 + zip 업로드 → GitHub Actions가 자동으로 글 작성·배포
- 초안 화면: 제목·본문·태그 복사 버튼, 번호 붙은 사진 내려받기, 본문의 `[사진 NN 넣기]` 자리표시

## 처음 한 번 설정

1. **Pages 켜기**: 저장소 **Settings → Pages → Build and deployment → Source** 를 `GitHub Actions` 로 선택
2. **Claude API 키 (선택)**: **Settings → Secrets and variables → Actions → New repository secret**
   - 이름 `ANTHROPIC_API_KEY`, 값은 Claude Console에서 만든 키
   - 키가 없거나, 잔액 부족·오류로 호출이 실패하면 **규칙 기반 작성기**로 자동 전환됩니다 (초안 상단에 안내 표시)
   - 모델을 바꾸려면 같은 화면 **Variables** 탭에 `CLAUDE_MODEL` (기본 `claude-sonnet-5-5`)
3. **업로드용 토큰**: GitHub **Settings → Developer settings → Fine-grained tokens → Generate new token**
   - Repository access: 이 저장소만
   - Permissions: **Contents: Read and write**, **Actions: Read-only**
   - 만든 토큰을 사이트의 `새 글 만들기 → GitHub 연결 설정`에 한 번 입력 (그 브라우저에만 저장)
4. **Actions → 블로그 초안 생성·배포 → Run workflow** 로 첫 배포. 주소는 `https://<계정>.github.io/culture-blog/`

## 사용법

1. 예매 페이지(놀티켓)에서 상세 이미지를 **원본 크기로 저장 → zip으로 압축**
   (이미지 파일 그대로 채팅·메신저에 올리면 축소되므로 zip 권장)
2. 사이트의 **새 글 만들기**에 링크와 zip을 넣고 **초안 만들기**
3. 1~3분 뒤 진행 상황 칸에 **만든 초안 열기** 버튼이 뜹니다

업로드 화면 대신 GitHub 웹에서 직접 해도 됩니다:
`requests/<아무ID>/` 폴더에 zip을 올리고, 같은 폴더에 `request.json` 을 `{"url": "https://nol.yanolja.com/ticket/products/26014046"}` 로 만들면 자동 실행됩니다.

## 구조

```
blogmaker/
  sources/    예매처 페이지 수집·파싱 (놀티켓, 인터파크 링크 → 놀티켓 변환)
  images/     zip 풀기 · 사진 후보 구역 자동 분할(XY-cut) · 자르기 · Claude용 후보 시트
  writers/    글 작성: claude.py(Claude API, 구조화 출력) → 실패 시 rules.py(규칙 기반)
  render/     게시글·홈·업로드 화면 HTML (templates/, static/)
  pipeline.py 요청 폴더 → content/posts/<ID>/ (post.json, img/, images.zip)
  models.py   수집 정보·초안·게시글 데이터 모델
requests/     업로드된 대기 요청 (처리되면 삭제)
content/posts 만들어진 게시글 데이터 (사이트는 매번 여기서 다시 생성)
```

### 작성 원칙
- 공연명·기간·시간·장소·연령·가격·티켓오픈·기획사 **정보 표는 예매 페이지 값만** 사용 (작성기가 바꾸지 않음)
- 사진은 코드가 찾은 후보 구역 중에서 **번호로만 선택** (좌표를 만들어내지 않음)
- 실제 관람 경험·감상은 쓰지 않고, 확인된 사실 기반 추천만. 제작사 수치는 출처 표기

## 로컬 실행

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python -m blogmaker local --url https://nol.yanolja.com/ticket/products/26014046 --zip 상세이미지.zip
python -m blogmaker site --out _site    # _site/index.html 열기
```
