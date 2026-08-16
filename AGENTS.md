# AIML Quant seminar agent guide

## Purpose

- 이 저장소는 AIML Quant 공개 세미나의 발표자료·상세 리포트·GitHub Pages를 관리한다.
- 공개 YouTube 영상과 세미나 페이지는 `slug` 로 연결한다.
- 기본 응답 언어는 한국어로 하되 코드·명령어·고유명사는 원문을 유지한다.

## 세미나와 스터디의 경계

| | 스터디 | 세미나 |
|---|---|---|
| 원자료 | 비공개 교재 (`study-materials`) | 공개 1차 자료 — 벤더 공식 문서·표준·논문·직접 측정 |
| 구조 | 교재의 장·절 순서를 보존 | 발표자가 구성한 섹션이 정본 |
| 주기 | 매주 회차가 이어짐 | 1회 완결 또는 파트 분할 |
| 저장소 | `study` + `study-materials` | `seminar` 하나 |

**`seminar-materials` 비공개 저장소는 만들지 않는다.** 원자료가 공개 웹이라 저작권 분리의 이유가
없다. 발표자가 만든 리포트·슬라이드·도해가 곧 자료이고 이 저장소에 공개된다. 이는
`management/ORGANIZATION.md` 의 초안 표(스터디 패턴 복사)에서 의도적으로 벗어난 결정이며
`management/DECISIONS.md` 에 근거가 있다.

## Repositories

- `aimlquant/seminar` (공개, 이 저장소): `html/` 공개 산출물과 `agent-support/` 도구
- 로컬은 `aimlquant/` 아래 `study/`, `media/` 와 나란히 둔다

저장소 이름이 곧 공개 URL 경로다. `seminar` → `https://aimlquant.github.io/seminar/`.

## Sources of truth

- `agent-support/site.toml`: 브랜드, 저장소, Pages, 공개 YouTube 채널
- `agent-support/seminars.toml`: 세미나 목록, 공개 경로, 공개 YouTube video ID
- `agent-support/templates/SEMINAR_SESSION_BLUEPRINT.md`: 리포트·덱 제작 절차
- `agent-support/templates/seminar-report/DESIGN.md`, `seminar-deck/DESIGN.md`: 형식 규칙

## File contract

```text
html/
├── index.html                  # 생성물. build_site.py 가 만든다
├── assets/                     # site.css, favicon.svg
└── seminars/<slug>/
    ├── index.html              # 생성물. 영상 임베드와 자료 링크
    ├── slides.html             # 손으로 만드는 발표 슬라이드
    ├── report.html             # 손으로 만드는 상세 리포트
    ├── seminar.toml            # 세미나 메타데이터
    └── assets/                 # 이 세미나에 귀속된 CSS·JS·figs 스냅샷
```

`index.html` 두 개는 생성물이다. 직접 편집하지 않는다. `build_site.py` 는 생성 표식이 없는
파일을 덮어쓰지 않고 실패한다.

## Safety boundaries

1. `youtube_video_id` 는 영상이 승인되어 실제 `public` 이 된 뒤에만 기록한다.
2. private 또는 unlisted video ID, OAuth 토큰, 쿠키, 클라이언트 비밀, 로컬 녹화 경로,
   업로드 복구 원장은 이 공개 저장소에 넣지 않는다.
3. **사내 색 토큰 `#A50034` · `#6E0022` 을 어떤 파일에도 남기지 않는다.** 사내 트랙에서 온
   원자료는 옮기기 전에 전수 치환한다. `validate-site.py` 가 게이트로 강제한다.
4. 사내 조직명·내부 제품 식별자·비공개 데모 계정을 공개 산출물에 남기지 않는다.
5. 세미나 `slug` 는 공개 URL이자 YouTube 설명란의 링크 대상이다. 한 번 정하면 바꾸지 않는다.
6. YouTube 설명은 해당 세미나 페이지를 링크하고, 세미나 페이지는 공개 영상만 링크한다.
7. 외부 CDN·외부 폰트·프레임워크에 의존하지 않는다. 세미나 폴더만으로 동작해야 한다.
8. 사용자 변경을 보존하고 관련 없는 파일을 되돌리지 않는다.
9. 커밋, push, Pages 설정 변경은 사용자가 요청한 범위에서만 수행한다.

## Workflow

새 세미나는 다음 순서로 만든다.

1. `agent-support/seminars.toml` 에 항목을 추가한다 (`status = "draft"`).
2. `python3 agent-support/scripts/new-seminar.py --seminar <id>` 로 스캐폴드한다.
3. 1차 자료를 감사하고 `report.html` 을 먼저 완성한다 — **리포트 게이트**.
4. 검증된 리포트에서 `slides.html` 을 파생한다.
5. `status = "published"` 로 바꾸고 `build_site.py` 로 목록과 세미나 페이지를 생성한다.
6. 영상이 public 이 된 뒤 `youtube_video_id` 를 기록하고 `media` 저장소에서 설명란을 갱신한다.

## Required verification

변경 뒤 다음을 실행한다.

```bash
python3 -m unittest discover -s agent-support/tests -v
python3 agent-support/scripts/build_site.py
python3 agent-support/scripts/build_site.py --check
python3 agent-support/scripts/validate-site.py --site html
git diff --check
```

HTML·CSS·SVG를 변경하면 실제 GitHub Pages 표시 크기의 데스크톱·모바일 렌더를 확인한다.
텍스트 잘림, 불균형, 깨진 링크, 영상 프레임 비율을 DOM 검사만으로 판정하지 않는다.
