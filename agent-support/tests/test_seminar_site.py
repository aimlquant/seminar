"""Contract tests for the seminar registry, templates, and build pipeline."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "agent-support" / "scripts"
TEMPLATES = REPO_ROOT / "agent-support" / "templates"
HTML = REPO_ROOT / "html"

INTERNAL_COLOR_RE = re.compile(r"#(?:A50034|6E0022)\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"{{[A-Z0-9_]+}}")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
VIDEO_ID_RE = re.compile(r"^[\w-]{11}$")


def run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def load(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load(REPO_ROOT / "agent-support" / "seminars.toml")
        self.site = load(REPO_ROOT / "agent-support" / "site.toml")

    def test_schema_version(self) -> None:
        self.assertEqual(self.registry["schema_version"], 1)
        self.assertEqual(self.site["schema_version"], 1)

    def test_site_declares_public_url(self) -> None:
        self.assertEqual(self.site["site"]["repository"], "aimlquant/seminar")
        self.assertTrue(self.site["site"]["pages_url"].endswith("/seminar/"))

    def test_seminar_ids_and_slugs_are_unique_and_safe(self) -> None:
        ids, slugs = set(), set()
        for item in self.registry["seminars"]:
            self.assertRegex(item["slug"], SLUG_RE)
            self.assertNotIn(item["id"], ids)
            self.assertNotIn(item["slug"], slugs)
            ids.add(item["id"])
            slugs.add(item["slug"])

    def test_video_ids_look_like_youtube_ids(self) -> None:
        for item in self.registry["seminars"]:
            video_id = item.get("youtube_video_id")
            if video_id is not None:
                self.assertRegex(video_id, VIDEO_ID_RE)

    def test_published_seminars_have_a_folder(self) -> None:
        for item in self.registry["seminars"]:
            if item.get("status") != "published":
                continue
            folder = HTML / "seminars" / item["slug"]
            self.assertTrue(folder.is_dir(), f"missing folder for {item['id']}")
            for name in ("index.html", "slides.html", "report.html", "seminar.toml"):
                self.assertTrue((folder / name).exists(), f"{item['id']} missing {name}")


class TemplateTest(unittest.TestCase):
    def template_files(self) -> list[Path]:
        return [
            path
            for path in TEMPLATES.rglob("*")
            if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".svg", ".tmpl"}
        ]

    def test_no_internal_color_tokens(self) -> None:
        for path in self.template_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(
                INTERNAL_COLOR_RE.search(text),
                f"internal color token in template {path.relative_to(REPO_ROOT)}",
            )

    def test_templates_declare_seminar_variants(self) -> None:
        deck = (TEMPLATES / "seminar-deck" / "index.html").read_text(encoding="utf-8")
        report = (TEMPLATES / "seminar-report" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-deck-template="seminar-deck-v1"', deck)
        self.assertIn('data-report-template="seminar-report-v1"', report)

    def test_template_tokens_are_known(self) -> None:
        known_html = {
            "{{DECK_TITLE}}",
            "{{SUBTITLE}}",
            "{{SERIES_TITLE}}",
            "{{PRESENTERS}}",
            "{{SCOPE}}",
            "{{DATE}}",
        }
        known_toml = {
            "{{SEMINAR_ID_TOML}}",
            "{{SLUG_TOML}}",
            "{{DECK_TITLE_TOML}}",
            "{{DATE_TOML}}",
            "{{PRESENTERS_TOML}}",
            "{{SECTIONS_TOML}}",
        }
        for name, known in (
            ("seminar-deck/index.html", known_html),
            ("seminar-report/index.html", known_html),
            ("seminar-deck/seminar.toml.tmpl", known_toml),
        ):
            found = set(TOKEN_RE.findall((TEMPLATES / name).read_text(encoding="utf-8")))
            self.assertTrue(found <= known, f"unknown token(s) in {name}: {found - known}")

    def test_design_documents_exist(self) -> None:
        for name in (
            "SEMINAR_SESSION_BLUEPRINT.md",
            "seminar-deck/DESIGN.md",
            "seminar-report/DESIGN.md",
        ):
            self.assertTrue((TEMPLATES / name).exists(), f"missing {name}")


class PipelineTest(unittest.TestCase):
    def test_build_site_is_idempotent(self) -> None:
        result = run("build_site.py", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_site_passes(self) -> None:
        result = run("validate-site.py", "--site", "html")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_seminar_refuses_existing_folder(self) -> None:
        result = run("new-seminar.py", "--seminar", "computer-use")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)

    def test_new_seminar_rejects_unknown_id(self) -> None:
        result = run("new-seminar.py", "--seminar", "does-not-exist")
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one registry entry", result.stderr)


class GeneratedPageTest(unittest.TestCase):
    def test_index_lists_published_seminars(self) -> None:
        text = (HTML / "index.html").read_text(encoding="utf-8")
        for item in load(REPO_ROOT / "agent-support" / "seminars.toml")["seminars"]:
            if item.get("status") != "published":
                continue
            self.assertIn(f'href="{item["slug"]}/"', text)
            self.assertIn(item["title_ko"], text)

    def test_seminar_pages_are_marked_generated(self) -> None:
        marker = "build_site.py 가 생성한다"
        self.assertIn(marker, (HTML / "index.html").read_text(encoding="utf-8"))
        for folder in (HTML / "seminars").iterdir():
            if folder.is_dir():
                self.assertIn(marker, (folder / "index.html").read_text(encoding="utf-8"))

    def test_index_links_back_to_the_landing_page(self) -> None:
        """이 저장소는 조직 랜딩의 하위 공간이다. 세미나 목록에서 랜딩으로
        돌아가는 링크가 눈에 보여야 방문자가 다른 공간을 찾을 수 있다."""
        site = load(REPO_ROOT / "agent-support" / "site.toml")["site"]
        text = (HTML / "index.html").read_text(encoding="utf-8")

        self.assertIn(
            f'<a class="back" href="{site["landing_url"]}">← AIML Quant 홈</a>',
            text,
        )

    def test_no_external_stylesheet_or_font(self) -> None:
        for path in HTML.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("fonts.googleapis.com", text)
            self.assertNotIn("cdn.jsdelivr.net", text)


if __name__ == "__main__":
    unittest.main()
