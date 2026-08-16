#!/usr/bin/env python3
"""Scaffold an AIML Quant seminar: paired long-form report and slide deck."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "agent-support" / "seminars.toml"
DEFAULT_SITE = REPO_ROOT / "html"
DEFAULT_DECK_TEMPLATE = REPO_ROOT / "agent-support" / "templates" / "seminar-deck"
DEFAULT_REPORT_TEMPLATE = REPO_ROOT / "agent-support" / "templates" / "seminar-report"

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
TOKEN_RE = re.compile(r"{{[A-Z0-9_]+}}")
CAPTION_NUMBER_RE = re.compile(r'asset-caption__chip">(?:\s*)(그림|표)\s+([1-9][0-9]*)')
MERGE_MARKER_RE = re.compile(r"(?m)^(?:<<<<<<<(?: .*)?|=======|>>>>>>>(?: .*)?)$")
INTERNAL_COLOR_RE = re.compile(r"#(?:A50034|6E0022)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seminar", required=True, help="Seminar id from seminars.toml")
    parser.add_argument(
        "--section", action="append", help="Deck section; repeat. Defaults to scope_ko"
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--template", type=Path, default=DEFAULT_DECK_TEMPLATE)
    parser.add_argument("--report-template", type=Path, default=DEFAULT_REPORT_TEMPLATE)
    return parser.parse_args()


def load_registry(path: Path) -> list[dict]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise ValueError(f"registry not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid registry TOML: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("seminars"), list):
        raise ValueError(f"unsupported seminar registry: {path}")
    return data["seminars"]


def render(source: str, replacements: dict[str, str], label: str) -> str:
    result = source
    for token, value in replacements.items():
        result = result.replace("{{" + token + "}}", value)
    unresolved = sorted(set(TOKEN_RE.findall(result)))
    if unresolved:
        raise ValueError(f"unresolved template token(s) in {label}: {unresolved}")
    return result


def toml_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def validate_template_sources(deck: Path, report: Path) -> None:
    for root in (deck, report):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {
                ".css",
                ".html",
                ".js",
                ".svg",
                ".tmpl",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if MERGE_MARKER_RE.search(text):
                raise ValueError(f"unresolved merge marker in template: {path}")
            if INTERNAL_COLOR_RE.search(text):
                raise ValueError(f"internal color token in template: {path}")

    deck_html = (deck / "index.html").read_text(encoding="utf-8")
    report_html = (report / "index.html").read_text(encoding="utf-8")

    deck_runtime = (deck / "assets" / "deck.js").read_text(encoding="utf-8")
    for contract in ("deckAppendix", "numberFigures", "deckFigureNumber"):
        if contract not in deck_runtime:
            raise ValueError(f"deck runtime is missing publication contract: {contract}")
    deck_script = deck_html.find('src="assets/deck.js"')
    lightbox_script = deck_html.find('src="assets/deck-lightbox.js"')
    if deck_script < 0 or lightbox_script < 0 or deck_script > lightbox_script:
        raise ValueError(
            "deck.js must run before deck-lightbox.js so active-mode figure numbers "
            "become accessible lightbox labels"
        )

    numbers: dict[str, list[int]] = {"그림": [], "표": []}
    for kind, number in CAPTION_NUMBER_RE.findall(report_html):
        numbers[kind].append(int(number))
    for kind, found in numbers.items():
        expected = list(range(1, len(found) + 1))
        if found != expected:
            raise ValueError(
                f"template {kind} caption numbers must be consecutive 1..N: "
                f"found {found}, expected {expected}"
            )


def main() -> int:
    args = parse_args()
    try:
        seminars = load_registry(args.registry.resolve())
        matches = [item for item in seminars if item.get("id") == args.seminar]
        if len(matches) != 1:
            raise ValueError(
                f"seminar id must match exactly one registry entry: {args.seminar}"
            )
        seminar = matches[0]

        slug = seminar.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
            raise ValueError(f"invalid seminar slug in registry: {slug!r}")
        try:
            date.fromisoformat(str(seminar.get("date")))
        except ValueError as exc:
            raise ValueError(f"seminar date must use YYYY-MM-DD: {seminar.get('date')!r}") from exc

        title = str(seminar.get("title_ko") or "").strip()
        if not title:
            raise ValueError("seminar title_ko must not be empty")
        subtitle = str(seminar.get("subtitle_ko") or "").strip()
        scope = str(seminar.get("scope_ko") or "").strip()
        series = str(seminar.get("series") or "AIML Quant 세미나").strip()
        presenters = [str(value).strip() for value in seminar.get("presenters", [])]
        if not presenters or any(not value for value in presenters):
            raise ValueError("seminar presenters must be a non-empty list")
        sections = [value.strip() for value in (args.section or [])]
        if not sections:
            sections = [part.strip() for part in scope.split("·") if part.strip()]
        if not sections:
            raise ValueError("provide --section or a non-empty scope_ko")

        deck_template = args.template.resolve()
        report_template = args.report_template.resolve()
        deck_html_template = deck_template / "index.html"
        metadata_template = deck_template / "seminar.toml.tmpl"
        report_html_template = report_template / "index.html"
        for required in (
            deck_html_template,
            metadata_template,
            deck_template / "assets",
            report_html_template,
            report_template / "assets",
        ):
            if not required.exists():
                raise ValueError(f"template component not found: {required}")
        validate_template_sources(deck_template, report_template)

        html_replacements = {
            "DECK_TITLE": html.escape(title),
            "SUBTITLE": html.escape(subtitle or scope),
            "SERIES_TITLE": html.escape(series),
            "PRESENTERS": html.escape(", ".join(presenters)),
            "SCOPE": html.escape(scope),
            "DATE": html.escape(str(seminar["date"])),
        }
        metadata_replacements = {
            "SEMINAR_ID_TOML": toml_value(args.seminar),
            "SLUG_TOML": toml_value(slug),
            "DECK_TITLE_TOML": toml_value(title),
            "DATE_TOML": toml_value(str(seminar["date"])),
            "PRESENTERS_TOML": toml_value(presenters),
            "SECTIONS_TOML": toml_value(sections),
        }

        deck_html = render(
            deck_html_template.read_text(encoding="utf-8"),
            html_replacements,
            deck_html_template.name,
        )
        report_html = render(
            report_html_template.read_text(encoding="utf-8"),
            html_replacements,
            f"{report_template.name}/{report_html_template.name}",
        )
        metadata = render(
            metadata_template.read_text(encoding="utf-8"),
            metadata_replacements,
            metadata_template.name,
        )

        target = args.site.resolve() / "seminars" / slug
        if target.exists():
            raise ValueError(f"seminar directory already exists: {target}")
        target.mkdir(parents=True)
        (target / "slides.html").write_text(deck_html, encoding="utf-8")
        (target / "report.html").write_text(report_html, encoding="utf-8")
        (target / "seminar.toml").write_text(metadata, encoding="utf-8")
        shutil.copytree(deck_template / "assets", target / "assets")
        shutil.copytree(report_template / "assets", target / "assets", dirs_exist_ok=True)
        (target / "assets" / "figs").mkdir(exist_ok=True)

        try:
            display = target.relative_to(REPO_ROOT)
        except ValueError:
            display = target
        print(f"created seminar report and deck: {display}")
        print(
            "next: follow agent-support/templates/SEMINAR_SESSION_BLUEPRINT.md; "
            "finish and validate report.html first, then derive slides.html from it. "
            "index.html is generated by build_site.py"
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
