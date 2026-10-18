"""Check public catalog ownership, mirrors, and the local reference graph."""

import importlib.util
import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "plugins/logfire/skills"
# Native-host onboarding uses plugin scripts and is intentionally not published
# as a standalone library specialist.
PLUGIN_ONLY_SKILLS = {"logfire-codex-connection"}
SPEC = importlib.util.spec_from_file_location(
    "skill_sources", ROOT / "scripts/logfire_skill_sources.py"
)
SOURCES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCES)


class SkillOwnershipTests(unittest.TestCase):
    def test_product_guides_are_owned_by_their_sdk_not_the_cli(self):
        sources = SOURCES.parse_sources(SOURCES.MANIFEST.read_text())
        self.assertEqual(
            sources["logfire-frontend"],
            {
                "repository": "pydantic/logfire-js",
                "path": "packages/logfire-browser/.agents/skills/logfire-frontend",
            },
        )
        self.assertEqual(
            sources["logfire-gateway"],
            {
                "repository": "pydantic/logfire",
                "path": "logfire-sdk/logfire/.agents/skills/logfire-gateway",
            },
        )
        cli_owned = {
            name
            for name, owner in sources.items()
            if owner["repository"] == "pydantic/logfire-cli"
        }
        self.assertEqual(cli_owned, {"logfire-coding-agents"})

    def test_every_published_skill_has_exactly_one_owner(self):
        sources = SOURCES.parse_sources(SOURCES.MANIFEST.read_text())
        published = {path.parent.name for path in CATALOG.glob("*/SKILL.md")}
        self.assertTrue(PLUGIN_ONLY_SKILLS <= published)
        self.assertEqual(set(sources), published - PLUGIN_ONLY_SKILLS)
        self.assertEqual(len(sources), 10)
        for name in PLUGIN_ONLY_SKILLS:
            self.assertFalse((ROOT / "skills" / name).exists())
        destinations = set()
        for name, source in sources.items():
            with self.subTest(name=name):
                destination = (source["repository"], source["path"])
                self.assertNotIn(destination, destinations)
                destinations.add(destination)
                self.assertIn(
                    source["repository"],
                    {
                        "pydantic/logfire",
                        "pydantic/logfire-js",
                        "pydantic/logfire-cli",
                        "pydantic/skills",
                    },
                )
                self.assertEqual(Path(source["path"]).name, name)
                if source["repository"] == "pydantic/skills":
                    self.assertEqual(ROOT / source["path"], CATALOG / name)
                plugin_files = {
                    path.relative_to(CATALOG / name): path.read_bytes()
                    for path in (CATALOG / name).rglob("*")
                    if path.is_file()
                }
                standalone_files = {
                    path.relative_to(ROOT / "skills" / name): path.read_bytes()
                    for path in (ROOT / "skills" / name).rglob("*")
                    if path.is_file()
                }
                self.assertEqual(plugin_files, standalone_files)

    def test_rejects_ambiguous_or_unsafe_owners(self):
        valid = {
            "repository": "pydantic/logfire-cli",
            "path": "skills/logfire-frontend",
        }
        for source in [
            {**valid, "repository": "another/owner"},
            {**valid, "repository": []},
            {**valid, "path": None},
            {**valid, "path": "/skills/logfire-frontend"},
            {**valid, "path": "../skills/logfire-frontend"},
            {**valid, "path": "skills//logfire-frontend"},
            {**valid, "path": "skills/logfire-frontend\n"},
            {**valid, "path": "skills/\u0000/logfire-frontend"},
            {**valid, "path": "skills/logfire-setup"},
            {**valid, "extra": "ignored"},
            {"repository": "pydantic/skills", "path": "skills/logfire-frontend"},
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                SOURCES.parse_sources(json.dumps({"logfire-frontend": source}))
        for contents in [
            "[]",
            "{}",
            "not json",
            '{"logfire-frontend":{},"logfire-frontend":{}}',
        ]:
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                SOURCES.parse_sources(contents)

    def test_valid_owners_keep_local_mcp_and_external_cli_sources_distinct(self):
        owners = {
            "logfire-frontend": {
                "repository": "pydantic/logfire-js",
                "path": "packages/logfire-browser/.agents/skills/logfire-frontend",
            },
            "logfire-query": {
                "repository": "pydantic/skills",
                "path": "plugins/logfire/skills/logfire-query",
            },
        }
        self.assertEqual(SOURCES.parse_sources(json.dumps(owners)), owners)

    def test_local_references_resolve_inside_the_published_catalog(self):
        for document in CATALOG.rglob("*.md"):
            for match in re.finditer(r"\]\(([^)\s]+)\)", document.read_text()):
                target = urlsplit(match[1])
                if target.scheme or target.netloc or not target.path:
                    continue
                with self.subTest(document=document, target=match[1]):
                    resolved = (document.parent / unquote(target.path)).resolve()
                    self.assertTrue(resolved.is_relative_to(CATALOG.resolve()))
                    self.assertTrue(resolved.is_file(), str(resolved))


if __name__ == "__main__":
    unittest.main()
