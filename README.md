# AIML Quant 세미나

교재 없이 한 주제를 끝까지 파는 공개 세미나. 발표자료와 상세 리포트를 함께 공개합니다.

- 공개 사이트: <https://aimlquant.github.io/seminar/>
- 조직 대문: <https://aimlquant.github.io/>
- 스터디: <https://aimlquant.github.io/study/>
- YouTube: <https://www.youtube.com/@aimlquant>

## 구조

| 경로 | 내용 |
|---|---|
| `html/` | GitHub Pages 에 그대로 배포되는 공개 산출물 |
| `html/seminars/<slug>/` | 세미나 한 편. 페이지·슬라이드·리포트·자산 |
| `agent-support/seminars.toml` | 세미나 레지스트리 |
| `agent-support/templates/` | 형식 정본 — 리포트·덱 템플릿과 DESIGN 문서 |
| `agent-support/scripts/` | 스캐폴드·빌드·검증 도구 |

## 한 세미나의 산출물

세미나 하나는 **상세 리포트와 발표 슬라이드의 쌍** 이다. 1차 자료를 먼저 리포트로 재구성해
검증하고, 그 리포트에서만 슬라이드를 파생한다. 리포트 없는 슬라이드 단독 산출물은 완료로 보지
않는다. 자세한 절차는 `agent-support/templates/SEMINAR_SESSION_BLUEPRINT.md` 를 본다.

## 새 세미나 만들기

```bash
# 1. agent-support/seminars.toml 에 항목 추가 (status = "draft")
python3 agent-support/scripts/new-seminar.py --seminar <id>
# 2. report.html 완성 → slides.html 파생 → status = "published"
python3 agent-support/scripts/build_site.py
```

## 검증

```bash
python3 -m unittest discover -s agent-support/tests -v
python3 agent-support/scripts/build_site.py --check
python3 agent-support/scripts/validate-site.py --site html
```
