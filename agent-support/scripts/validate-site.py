#!/usr/bin/env python3
"""Validate the public seminar site: contracts, self-containment, and safety."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
SEMINARS_TOML = REPO_ROOT / "agent-support" / "seminars.toml"

INTERNAL_COLOR_RE = re.compile(r"#(?:A50034|6E0022)\b", re.IGNORECASE)
CSS_REMOTE_URL_RE = re.compile(r"url\(\s*['\"]?(https?:)?//", re.IGNORECASE)
RESOURCE_TAGS = {"link": "href", "script": "src", "img": "src", "iframe": "src"}
LOADED_LINK_RELS = {"stylesheet", "icon", "shortcut", "preload", "manifest", "apple-touch-icon"}
ALLOWED_REMOTE_FRAME_HOSTS = {"www.youtube-nocookie.com", "www.youtube.com"}
REQUIRED_FILES = ("index.html", "slides.html", "report.html", "seminar.toml")
GENERATED_PAGES = ("index.html",)


class PageParser(HTMLParser):
    """Collect the contracts validate-site.py needs from one HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.slides: list[dict[str, str]] = []
        self.report_sections: list[str] = []
        self.required_figures: list[tuple[str, str]] = []  # (figure id, img src)
        self.images: list[str] = []
        self.resources: list[tuple[str, str]] = []  # (tag, url)
        self.caption_numbers: dict[str, list[int]] = {"그림": [], "표": []}
        self.report_source: str | None = None
        self._chip_depth = 0
        self._chip_text: list[str] = []
        self._figure_stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        classes = attr.get("class", "").split()

        if "id" in attr and attr["id"]:
            self.ids.add(attr["id"])
        if tag == "main" and attr.get("data-report-source"):
            self.report_source = attr["data-report-source"]
        if tag == "section" and "slide" in classes:
            self.slides.append(
                {
                    "aria-label": attr.get("aria-label", ""),
                    "data-report-refs": attr.get("data-report-refs", ""),
                }
            )
        if tag == "section" and "report-section" in classes and attr.get("id"):
            self.report_sections.append(attr["id"])
        if tag == "figure":
            self._figure_stack.append(
                {
                    "id": attr.get("id", ""),
                    "required": attr.get("data-deck-use") == "required",
                    "src": "",
                }
            )
        if tag == "img":
            src = attr.get("src", "")
            self.images.append(src)
            if self._figure_stack and not self._figure_stack[-1]["src"]:
                self._figure_stack[-1]["src"] = src
        if tag in RESOURCE_TAGS:
            url = attr.get(RESOURCE_TAGS[tag], "")
            rels = set(attr.get("rel", "").lower().split())
            loads_asset = tag != "link" or bool(rels & LOADED_LINK_RELS)
            if url and loads_asset:
                self.resources.append((tag, url))
        if "asset-caption__chip" in classes:
            self._chip_depth = 1
            self._chip_text = []
        elif self._chip_depth:
            self._chip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "figure" and self._figure_stack:
            figure = self._figure_stack.pop()
            if figure["required"]:
                self.required_figures.append((str(figure["id"]), str(figure["src"])))
        if self._chip_depth:
            self._chip_depth -= 1
            if self._chip_depth == 0:
                text = "".join(self._chip_text).strip()
                match = re.fullmatch(r"(그림|표)\s*([0-9]+)", text)
                if match:
                    self.caption_numbers[match.group(1)].append(int(match.group(2)))

    def handle_data(self, data: str) -> None:
        if self._chip_depth:
            self._chip_text.append(data)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def check_no_internal_colors(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".html", ".css", ".js", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = INTERNAL_COLOR_RE.findall(text)
        if hits:
            rel = path.relative_to(root.parent)
            errors.append(f"{rel}: internal color token appears {len(hits)} time(s)")


def check_no_remote_assets(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*.css")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if CSS_REMOTE_URL_RE.search(text):
            errors.append(f"{path.relative_to(root.parent)}: CSS loads a remote url()")
    for path in sorted(root.rglob("*.html")):
        page = parse_page(path)
        rel = path.relative_to(root.parent)
        for tag, url in page.resources:
            parsed = urlparse(url)
            if not parsed.scheme and not url.startswith("//"):
                continue
            if parsed.scheme == "data":
                continue
            if tag == "iframe" and parsed.netloc in ALLOWED_REMOTE_FRAME_HOSTS:
                continue
            errors.append(f"{rel}: <{tag}> loads a remote asset: {url}")


def check_internal_links(path: Path, site: Path, errors: list[str]) -> None:
    page = parse_page(path)
    rel = path.relative_to(site.parent)
    for _tag, url in page.resources:
        parsed = urlparse(url)
        if parsed.scheme or url.startswith("//") or url.startswith("#"):
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        if not target.exists():
            errors.append(f"{rel}: missing local asset {url}")


def check_caption_numbers(page: PageParser, label: str, errors: list[str]) -> None:
    for kind, found in page.caption_numbers.items():
        expected = list(range(1, len(found) + 1))
        if found != expected:
            errors.append(
                f"{label}: {kind} caption numbers must be 1..N without gaps; "
                f"found {found}"
            )


def check_seminar(folder: Path, entry: dict, site: Path, errors: list[str]) -> None:
    rel = folder.relative_to(site.parent)
    for name in REQUIRED_FILES:
        if not (folder / name).exists():
            errors.append(f"{rel}: missing required file {name}")
    if any(not (folder / name).exists() for name in REQUIRED_FILES):
        return

    with (folder / "seminar.toml").open("rb") as stream:
        meta = tomllib.load(stream)
    for field, expected in (
        ("slug", entry["slug"]),
        ("title", entry["title_ko"]),
        ("date", str(entry["date"])),
    ):
        if str(meta.get(field)) != str(expected):
            errors.append(
                f"{rel}/seminar.toml: {field} is {meta.get(field)!r}, "
                f"registry says {expected!r}"
            )
    if meta.get("report_source") != "report.html":
        errors.append(f"{rel}/seminar.toml: report_source must be report.html")

    deck = parse_page(folder / "slides.html")
    report = parse_page(folder / "report.html")

    if deck.report_source != "report.html":
        errors.append(f"{rel}/slides.html: <main> must set data-report-source=\"report.html\"")
    if not deck.slides:
        errors.append(f"{rel}/slides.html: no .slide sections found")

    referenced: set[str] = set()
    for index, slide in enumerate(deck.slides, 1):
        if not slide["aria-label"].strip():
            errors.append(f"{rel}/slides.html: slide {index} has no aria-label")
        refs = slide["data-report-refs"].split()
        if not refs:
            errors.append(f"{rel}/slides.html: slide {index} has no data-report-refs")
            continue
        for ref in refs:
            referenced.add(ref)
            if ref not in report.ids:
                errors.append(
                    f"{rel}/slides.html: slide {index} references unknown report id {ref!r}"
                )

    for section_id in report.report_sections:
        if section_id not in referenced:
            errors.append(
                f"{rel}: report section {section_id!r} is never referenced by a slide"
            )

    deck_images = set(deck.images)
    for figure_id, src in report.required_figures:
        if src and src not in deck_images:
            errors.append(
                f"{rel}: required figure {figure_id!r} image {src!r} is missing from the deck"
            )

    check_caption_numbers(report, f"{rel}/report.html", errors)

    check_caption_numbers(deck, f"{rel}/slides.html", errors)

    for name in REQUIRED_FILES:
        if name.endswith(".html"):
            check_internal_links(folder / name, site, errors)

    video_id = entry.get("youtube_video_id")
    if video_id:
        page_text = (folder / "index.html").read_text(encoding="utf-8")
        if video_id not in page_text:
            errors.append(
                f"{rel}/index.html: registry lists video {video_id} "
                f"but the seminar page never embeds it"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=REPO_ROOT / "html")
    args = parser.parse_args()
    site = args.site.resolve()

    errors: list[str] = []
    try:
        with SEMINARS_TOML.open("rb") as stream:
            registry = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    seminars = registry.get("seminars", [])
    known_videos = {
        str(item["youtube_video_id"])
        for item in seminars
        if item.get("youtube_video_id")
    }

    check_no_internal_colors(site, errors)
    check_no_remote_assets(site, errors)
    check_internal_links(site / "index.html", site, errors)

    seminar_root = site / "seminars"
    on_disk = {p.name for p in seminar_root.iterdir() if p.is_dir()} if seminar_root.exists() else set()
    for entry in seminars:
        if entry.get("status") != "published":
            continue
        folder = seminar_root / str(entry["slug"])
        if not folder.is_dir():
            errors.append(f"published seminar {entry['id']} has no folder at {folder}")
            continue
        on_disk.discard(folder.name)
        check_seminar(folder, entry, site, errors)
    for orphan in sorted(on_disk):
        errors.append(f"html/seminars/{orphan} is not a published seminar in seminars.toml")

    video_pattern = re.compile(r"youtube(?:-nocookie)?\.com/(?:watch\?v=|embed/)([\w-]{11})")
    for path in sorted(site.rglob("*.html")):
        for found in video_pattern.findall(path.read_text(encoding="utf-8")):
            if found not in known_videos:
                errors.append(
                    f"{path.relative_to(site.parent)}: video id {found} is not in seminars.toml"
                )

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        print(f"\n{len(errors)} problem(s) found", file=sys.stderr)
        return 1

    published = sum(1 for item in seminars if item.get("status") == "published")
    print(f"validated {published} published seminar(s): no problems found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
