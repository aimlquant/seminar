#!/usr/bin/env python3
"""Generate the public seminar index from agent-support registries."""

from __future__ import annotations

import argparse
import html
import sys
import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SITE = REPO_ROOT / "html"
SITE_TOML = REPO_ROOT / "agent-support" / "site.toml"
SEMINARS_TOML = REPO_ROOT / "agent-support" / "seminars.toml"

GENERATED_NOTE = (
    "<!-- 이 파일은 agent-support/scripts/build_site.py 가 생성한다. 직접 편집하지 않는다. -->"
)


def load_toml(path: Path, key: str, kind: type) -> dict:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise ValueError(f"registry not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version in {path}")
    if not isinstance(data.get(key), kind):
        raise ValueError(f"{path} must define {key}")
    return data


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def format_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.year}년 {parsed.month}월 {parsed.day}일"


def validate_seminar(item: dict, index: int) -> None:
    required = ("id", "slug", "title_ko", "date", "presenters", "status")
    for field in required:
        if not item.get(field):
            raise ValueError(f"seminars[{index}] is missing {field}")
    if item["status"] not in {"published", "draft", "scheduled"}:
        raise ValueError(f"seminars[{index}] has unknown status: {item['status']}")
    date.fromisoformat(str(item["date"]))
    video_id = item.get("youtube_video_id")
    if video_id is not None and not isinstance(video_id, str):
        raise ValueError(f"seminars[{index}] youtube_video_id must be a string")


def render_links(item: dict) -> str:
    parts: list[str] = []
    for artifact in item.get("artifacts", []):
        label = esc(artifact.get("label") or artifact.get("kind"))
        url = esc(artifact.get("url"))
        primary = " card-link--primary" if artifact.get("kind") == "slides" else ""
        parts.append(f'<a class="card-link{primary}" href="{url}">{label}</a>')
    video_id = item.get("youtube_video_id")
    if video_id:
        url = f"https://www.youtube.com/watch?v={esc(video_id)}"
        parts.append(
            f'<a class="card-link" href="{url}" target="_blank" '
            f'rel="noopener noreferrer">영상 보기 ↗</a>'
        )
    return "".join(parts)


def render_card(item: dict) -> str:
    meta: list[str] = [f"<span>{esc(format_date(str(item['date'])))}</span>"]
    duration = item.get("duration_minutes")
    if duration:
        meta.append(f"<span>{esc(duration)}분</span>")
    meta.append(f"<span>{esc(' · '.join(item.get('presenters', [])))}</span>")

    subtitle = item.get("subtitle_ko")
    summary = item.get("summary_ko")
    scope = item.get("scope_ko")

    lines = [
        '      <article class="card">',
        f'        <h3><a href="{esc(item["slug"])}/">{esc(item["title_ko"])}</a></h3>',
    ]
    if subtitle:
        lines.append(f'        <p class="card-subtitle">{esc(subtitle)}</p>')
    lines.append(f'        <p class="card-meta">{"".join(meta)}</p>')
    if summary:
        lines.append(f"        <p class=\"card-summary\">{esc(summary)}</p>")
    if scope:
        lines.append(f'        <p class="card-scope">{esc(scope)}</p>')
    lines.append(f'        <p class="card-links">{render_links(item)}</p>')
    lines.append("      </article>")
    return "\n".join(lines)


def render_seminar_page(site: dict, item: dict) -> str:
    """Render the seminar landing page: video, summary, and links to the artifacts."""
    meta: list[str] = [f"<span>{esc(format_date(str(item['date'])))}</span>"]
    duration = item.get("duration_minutes")
    if duration:
        meta.append(f"<span>{esc(duration)}분</span>")
    meta.append(f"<span>{esc(' · '.join(item.get('presenters', [])))}</span>")

    video_id = item.get("youtube_video_id")
    if video_id:
        watch = f"https://www.youtube.com/watch?v={esc(video_id)}"
        video_block = (
            '    <div class="video-frame">\n'
            f'      <iframe src="https://www.youtube-nocookie.com/embed/{esc(video_id)}"\n'
            f'        title="{esc(item["title_ko"])} 발표 영상" loading="lazy"\n'
            '        allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"\n'
            '        allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>\n'
            "    </div>"
        )
        video_link = (
            f'<a class="card-link" href="{watch}" target="_blank" '
            f'rel="noopener noreferrer">YouTube에서 보기 ↗</a>'
        )
    else:
        video_block = '    <p class="note">공개 영상은 준비 중입니다.</p>'
        video_link = ""

    links = [
        '<a class="card-link card-link--primary" href="slides.html">발표자료 보기</a>',
        '<a class="card-link" href="report.html">상세 리포트</a>',
    ]
    if video_link:
        links.append(video_link)

    subtitle = item.get("subtitle_ko")
    summary = item.get("summary_ko")
    scope = item.get("scope_ko")

    body: list[str] = []
    if subtitle:
        body.append(f'    <p class="lead">{esc(subtitle)}</p>')
    body.append(f'    <p class="card-meta page-meta">{"".join(meta)}</p>')
    body.append(video_block)
    body.append(f'    <p class="page-links">{"".join(links)}</p>')
    if summary:
        body.append(f'    <p class="page-summary">{esc(summary)}</p>')
    if scope:
        body.append(f'    <p class="card-scope">{esc(scope)}</p>')

    canonical = f"{site['pages_url']}seminars/{item['slug']}/"
    description = summary or subtitle or item["title_ko"]
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(item['title_ko'])} · {esc(site['space_ko'])} · {esc(site['name_ko'])}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="../../assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="../../assets/site.css">
</head>
<body>
{GENERATED_NOTE}
  <main class="shell">
    <div class="brand">
      <a class="brand-name" href="../../">AIML Quant</a>
      <span class="brand-sub">SEMINAR</span>
    </div>

    <h1>{esc(item['title_ko'])}</h1>
{chr(10).join(body)}

    <div class="links">
      <a class="button button--ghost" href="../../">← 세미나 목록</a>
      <a class="button button--ghost" href="{esc(site['youtube_url'])}" target="_blank" rel="noopener noreferrer">YouTube 채널 ↗</a>
      <a class="button button--ghost" href="{esc(site['kakao_openchat_url'])}" target="_blank" rel="noopener noreferrer">카카오 오픈채팅 ↗</a>
    </div>
    <p class="note">
      오픈채팅 입장에는 참가 코드가 필요합니다.
      <a href="mailto:{esc(site['contact_email'])}">{esc(site['contact_email'])}</a>
      으로 메일 주시면 안내해 드립니다.
    </p>
  </main>
</body>
</html>
"""


def render_index(site: dict, seminars: list[dict]) -> str:
    published = [item for item in seminars if item.get("status") == "published"]
    published.sort(key=lambda item: (str(item["date"]), str(item["id"])), reverse=True)

    groups: list[tuple[str, list[dict]]] = []
    for item in published:
        series = str(item.get("series") or "단독 세미나")
        if groups and groups[-1][0] == series:
            groups[-1][1].append(item)
        else:
            groups.append((series, [item]))

    sections: list[str] = []
    for series, items in groups:
        cards = "\n".join(render_card(item) for item in items)
        count = len(items)
        sections.append(
            f'    <section class="series">\n'
            f'      <h2 class="series-title">{esc(series)}'
            f'<span class="series-count">{count}편</span></h2>\n'
            f"{cards}\n"
            f"    </section>"
        )
    if not sections:
        sections.append(
            '    <section class="series"><p class="empty">공개된 세미나가 아직 없습니다.</p></section>'
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>세미나 · {esc(site['name_ko'])}</title>
  <meta name="description" content="{esc(site['tagline_ko'])}">
  <link rel="canonical" href="{esc(site['pages_url'])}">
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
{GENERATED_NOTE}
  <main class="shell">
    <div class="brand">
      <span class="brand-name">AIML Quant</span>
      <span class="brand-sub">SEMINAR</span>
    </div>
    <a class="back" href="{esc(site['landing_url'])}">← AIML Quant 홈</a>

    <h1>세미나</h1>
    <p class="lead">{esc(site['tagline_ko'])}</p>

{chr(10).join(sections)}

    <div class="links">
      <a class="button" href="{esc(site['youtube_url'])}" target="_blank" rel="noopener noreferrer">YouTube 채널 ↗</a>
      <a class="button button--ghost" href="{esc(site['study_url'])}">스터디</a>
      <a class="button button--ghost" href="{esc(site['kakao_openchat_url'])}" target="_blank" rel="noopener noreferrer">카카오 오픈채팅 ↗</a>
      <a class="button button--ghost" href="https://github.com/{esc(site['repository'])}" target="_blank" rel="noopener noreferrer">GitHub ↗</a>
    </div>
    <p class="note">
      오픈채팅 입장에는 참가 코드가 필요합니다.
      <a href="mailto:{esc(site['contact_email'])}">{esc(site['contact_email'])}</a>
      으로 메일 주시면 안내해 드립니다.
    </p>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument(
        "--check", action="store_true", help="Fail when the built index differs from disk"
    )
    args = parser.parse_args()

    try:
        site = load_toml(SITE_TOML, "site", dict)["site"]
        seminars = load_toml(SEMINARS_TOML, "seminars", list)["seminars"]
        seen: set[str] = set()
        for index, item in enumerate(seminars):
            validate_seminar(item, index)
            for key in ("id", "slug"):
                token = f"{key}:{item[key]}"
                if token in seen:
                    raise ValueError(f"duplicate seminar {key}: {item[key]}")
                seen.add(token)

        site_root = args.site.resolve()
        outputs: dict[Path, str] = {site_root / "index.html": render_index(site, seminars)}
        for item in seminars:
            if item.get("status") != "published":
                continue
            folder = site_root / "seminars" / str(item["slug"])
            if not folder.is_dir():
                raise ValueError(
                    f"published seminar {item['id']} has no folder at {folder}; "
                    f"run new-seminar.py first"
                )
            outputs[folder / "index.html"] = render_seminar_page(site, item)

        if args.check:
            stale = [
                path
                for path, content in outputs.items()
                if (path.read_text(encoding="utf-8") if path.exists() else "") != content
            ]
            if stale:
                for path in stale:
                    print(f"ERROR: {path.relative_to(REPO_ROOT)} is stale", file=sys.stderr)
                print("run build_site.py to regenerate", file=sys.stderr)
                return 1
            print(f"{len(outputs)} generated page(s) are up to date")
            return 0

        for path in outputs:
            if path.exists() and GENERATED_NOTE not in path.read_text(encoding="utf-8"):
                raise ValueError(
                    f"refusing to overwrite hand-authored file: {path.relative_to(REPO_ROOT)}"
                )
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        nojekyll = site_root / ".nojekyll"
        if not nojekyll.exists():
            nojekyll.write_text("", encoding="utf-8")
        published = sum(1 for item in seminars if item.get("status") == "published")
        print(f"built {len(outputs)} page(s) for {published} published seminar(s)")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
