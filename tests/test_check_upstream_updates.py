"""Contract tests for tools/check_upstream_updates.py (no network, no git remote)."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_upstream_updates", ROOT / "tools" / "check_upstream_updates.py"
)
assert _SPEC is not None and _SPEC.loader is not None
upstream = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = upstream
_SPEC.loader.exec_module(upstream)

SHA = "a" * 40


def write_baseline(body: object) -> Path:
    directory = Path(tempfile.mkdtemp())
    path = directory / "baseline.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


class BaselineValidationTests(unittest.TestCase):
    def good(self, **override: object) -> dict:
        data = {"repo": "r", "branch": "main", "reviewed_through": SHA, "reviewed_date": "d"}
        data.update(override)
        return data

    def test_valid_baseline_loads(self) -> None:
        self.assertEqual(upstream.load_baseline(write_baseline(self.good()))["branch"], "main")

    def test_malformed_baseline_is_reported_not_a_traceback(self) -> None:
        # main() only turns UpstreamCheckError into a "Check failed" report.
        for body in ([], "text", self.good(reviewed_through=5), self.good(reviewed_through=None)):
            with self.subTest(body=body):
                with self.assertRaises(upstream.UpstreamCheckError):
                    upstream.load_baseline(write_baseline(body))

    def test_short_sha_and_unknown_track_are_rejected(self) -> None:
        for override in ({"reviewed_through": "abc"}, {"track": "nightly"}):
            with self.subTest(override=override):
                with self.assertRaises(upstream.UpstreamCheckError):
                    upstream.load_baseline(write_baseline(self.good(**override)))


class TagParsingTests(unittest.TestCase):
    def test_peeled_commit_wins_and_non_semver_tags_are_skipped(self) -> None:
        raw = (
            f"{'1' * 40}\trefs/tags/v1.0.9\n"
            f"{'2' * 40}\trefs/tags/v1.0.10\n"
            f"{'3' * 40}\trefs/tags/v1.0.10^{{}}\n"
            f"{'4' * 40}\trefs/tags/nightly\n"
        )
        parsed = upstream.parse_tag_refs(raw)
        self.assertEqual([item[1] for item in parsed], ["v1.0.9", "v1.0.10"])  # 10 > 9 numerically
        self.assertEqual(parsed[-1][2], "3" * 40)


class SlugAndRenderingTests(unittest.TestCase):
    def test_upstream_slug(self) -> None:
        self.assertEqual(upstream.upstream_slug("https://github.com/o/n.git"), "o/n")
        self.assertEqual(upstream.upstream_slug("git@github.com:o/n"), "o/n")
        self.assertIsNone(upstream.upstream_slug("https://example.com/o/n"))

    def test_pipe_in_a_ticket_title_cannot_break_the_table(self) -> None:
        lines = upstream.render_ticket_section(
            "PRs", 1, [{"number": 2, "title": "a | b"}], "pr", "docs/DECISIONS.md"
        )
        self.assertIn(r"| #2 | a \| b |", lines)

    def test_unchecked_tickets_are_not_reported_as_clean(self) -> None:
        text = "\n".join(upstream.render_ticket_section("PRs", 1, None, "pr", "log"))
        self.assertIn("Not checked", text)
        self.assertNotIn("No new items", text)


if __name__ == "__main__":
    unittest.main()
