"""Report upstream work that has not yet been reviewed by this fork.

Two tracking modes, selected by ``track`` in ``tools/upstream_baseline.json``:

``commit``
    Everything on the upstream branch past ``reviewed_through``. This fork
    tracks the branch, because upstream releases are merged in as version
    bumps and a tag alone would hide the changes that led up to them.

``release``
    Only what upstream has tagged with a semantic version, compared against
    ``reviewed_through`` (the tagged commit).

Pull requests and issues are read as well, closed ones included, against
``reviewed_pr_through`` and ``reviewed_issue_through``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BASELINE_PATH = SCRIPT_DIR / "upstream_baseline.json"
UPSTREAM_REF_PREFIX = "refs/upstream-check"
DEFAULT_DECISION_LOG = "docs/DECISIONS.md"
TRACK_MODES = ("release", "commit")
_SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpstreamCheckError(RuntimeError):
    """Raised when the baseline or upstream Git history cannot be inspected."""


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    if not path.is_file():
        raise UpstreamCheckError(f"missing baseline file: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpstreamCheckError(f"invalid baseline file: {path}: {exc}") from exc
    required = {"repo", "branch", "reviewed_through", "reviewed_date"}
    missing = sorted(required - baseline.keys())
    if missing:
        raise UpstreamCheckError(f"baseline missing fields: {', '.join(missing)}")
    if len(baseline["reviewed_through"]) != 40:
        raise UpstreamCheckError("reviewed_through must be a full 40-character SHA")
    track = baseline.get("track", "release")
    if track not in TRACK_MODES:
        raise UpstreamCheckError(f"track must be one of {', '.join(TRACK_MODES)}, not {track!r}")
    return baseline


def parse_tag_refs(raw: str) -> list[tuple[tuple[int, int, int], str, str]]:
    """Parse ``git ls-remote --tags`` output into sorted (version, tag, sha).

    Annotated tags appear twice: the tag object, then the peeled ``^{}`` line
    carrying the commit. The peeled line wins, because the commit is what the
    baseline records.
    """
    commits: dict[str, str] = {}
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        sha, ref = line.split("\t", 1)
        name = ref.strip().removeprefix("refs/tags/")
        peeled = name.endswith("^{}")
        name = name.removesuffix("^{}")
        if not _SEMVER_TAG_RE.match(name):
            continue
        if peeled or name not in commits:
            commits[name] = sha.strip()

    parsed = []
    for name, sha in commits.items():
        match = _SEMVER_TAG_RE.match(name)
        if match is None:  # pragma: no cover - filtered above
            continue
        parsed.append((tuple(int(part) for part in match.groups()), name, sha))
    return sorted(parsed)


def latest_upstream_release(baseline: dict, repo_dir: Path) -> tuple[str, str] | None:
    """Return the highest semver tag upstream publishes, as (tag, commit sha)."""
    raw = run_git(["ls-remote", "--tags", baseline["repo"]], repo_dir)
    tags = parse_tag_refs(raw)
    if not tags:
        return None
    _, name, sha = tags[-1]
    return name, sha


def run_git(args: list[str], repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise UpstreamCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def fetch_upstream(baseline: dict, repo_dir: Path) -> str:
    branch = baseline["branch"]
    ref = f"{UPSTREAM_REF_PREFIX}/{branch}"
    run_git(
        ["fetch", "--quiet", baseline["repo"], f"+refs/heads/{branch}:{ref}"],
        repo_dir,
    )
    return ref


def fetch_upstream_release(baseline: dict, repo_dir: Path, tag: str) -> str:
    ref = f"{UPSTREAM_REF_PREFIX}/tags/{tag}"
    run_git(
        ["fetch", "--quiet", baseline["repo"], f"+refs/tags/{tag}:{ref}"],
        repo_dir,
    )
    return ref


def fork_status(baseline: dict, repo_dir: Path, upstream_ref: str) -> dict:
    """How far this fork has moved from the reviewed baseline, and upstream too.

    These counts change with every commit on either side, so they are computed
    when the report is read rather than written into a document, where they
    would be wrong by the time anyone looked. The baseline SHA in
    `upstream_baseline.json` is the part that is a decision and does belong in
    version control.
    """
    reviewed = baseline["reviewed_through"]

    def count(rev_range: str) -> int:
        return int(run_git(["rev-list", "--count", rev_range], repo_dir).strip())

    return {
        "baseline": reviewed[:7],
        "fork_head": run_git(["rev-parse", "--short", "HEAD"], repo_dir).strip(),
        "upstream_tip": run_git(["rev-parse", "--short", upstream_ref], repo_dir).strip(),
        "ahead": count(f"{reviewed}..HEAD"),
        "behind": count(f"{reviewed}..{upstream_ref}"),
    }


def render_fork_status(status: dict | None, error: str | None = None) -> list[str]:
    if status is None:
        return ["## Fork status", "", f"無法計算：{error or 'unknown'}", ""]
    return [
        "## Fork status",
        "",
        f"- 共同 baseline：`{status['baseline']}`（已審視至此）",
        f"- 本 fork `HEAD`：`{status['fork_head']}`，baseline 之後 **ahead {status['ahead']}**",
        f"- upstream tip：`{status['upstream_tip']}`，baseline 之後 **behind {status['behind']}**",
        "",
        "這兩個數字每次 commit 都會變，所以由本檢查當場算出，不寫進文件。",
        "",
    ]


def collect_new_commits(baseline: dict, repo_dir: Path, ref: str) -> list[dict]:
    reviewed = baseline["reviewed_through"]
    raw = run_git(
        [
            "log",
            "--reverse",
            "--date=short",
            "--format=%H%x1f%ad%x1f%s",
            f"{reviewed}..{ref}",
        ],
        repo_dir,
    )
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split("\x1f", 2)
        files = [
            item
            for item in run_git(
                ["show", "--name-only", "--format=", sha], repo_dir
            ).splitlines()
            if item.strip()
        ]
        commits.append(
            {
                "sha": sha,
                "short": sha[:7],
                "date": date,
                "subject": subject,
                "files": files,
            }
        )
    return commits



def upstream_slug(repo_url: str) -> str | None:
    """`https://github.com/owner/name.git` -> `owner/name`, or None if not GitHub."""
    match = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$", repo_url
    )
    return f"{match['owner']}/{match['name']}" if match else None


def collect_new_tickets(baseline: dict, kind: str) -> list[dict] | None:
    """All PRs or issues numbered above the watermark, closed ones included.

    Returns ``None`` -- not an empty list -- when ``gh`` cannot answer, and the
    report says so. "Not checked" and "nothing to review" look identical in a
    green report, and only one of them is true; conflating them is how a fork
    stops noticing upstream without anybody deciding to.
    """
    slug = upstream_slug(str(baseline["repo"]))
    if not slug:
        return None
    watermark = int(baseline.get(f"reviewed_{kind}_through", 0) or 0)
    try:
        result = subprocess.run(
            [
                "gh", kind, "list", "--repo", slug, "--state", "all",
                "--limit", "50", "--json", "number,title",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            # `errors` is not optional here. Ticket titles are written by
            # strangers and the console this runs on is not always UTF-8;
            # without it a single undecodable byte raises UnicodeDecodeError and
            # the whole upstream check dies instead of reporting what it read.
            errors="replace",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        items = json.loads(result.stdout)
    except ValueError:
        return None
    return sorted(
        (item for item in items if item["number"] > watermark),
        key=lambda item: item["number"],
    )


def render_ticket_section(
    title: str,
    watermark: int,
    tickets: list[dict] | None,
    kind: str,
    decision_log: str,
) -> list[str]:
    lines = [f"## {title}", "", f"Triaged through `#{watermark}`.", ""]
    if tickets is None:
        lines.extend(
            [
                "Not checked: `gh` was unavailable, unauthenticated, or the baseline",
                "does not name a GitHub repository. Reported as such rather than as",
                '"nothing to review" -- the difference matters.',
                "",
            ]
        )
        return lines
    if not tickets:
        lines.extend(["No new items above that number.", ""])
        return lines
    lines.extend(
        [
            f"{len(tickets)} new item(s) to triage.",
            "",
            "| Item | Title |",
            "| --- | --- |",
        ]
    )
    for ticket in tickets:
        # The escape is computed outside the f-string: a backslash inside an
        # f-string expression is a SyntaxError before Python 3.12.
        item_title = ticket["title"].replace("|", "\\|")
        lines.append(f"| #{ticket['number']} | {item_title} |")
    lines.extend(
        [
            "",
            f"Record the verdict in `{decision_log}`, then raise",
            f"`reviewed_{kind}_through` so the same item is never re-triaged.",
            "",
        ]
    )
    return lines


def append_ticket_sections(
    report: str, baseline: dict, prs: list[dict] | None, issues: list[dict] | None
) -> str:
    """Add the pull-request and issue sections to an existing commit report.

    Appending rather than restructuring keeps each fork's own commit-section
    wording (and its own hardening) intact.
    """
    decision_log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    lines = [report.rstrip("\n"), ""]
    lines += render_ticket_section(
        "Upstream pull requests",
        int(baseline.get("reviewed_pr_through", 0) or 0),
        prs,
        "pr",
        decision_log,
    )
    lines += render_ticket_section(
        "Upstream issues",
        int(baseline.get("reviewed_issue_through", 0) or 0),
        issues,
        "issue",
        decision_log,
    )
    return "\n".join(lines)

def render_markdown(
    baseline: dict,
    commits: list[dict],
    error: str | None = None,
    release: str | None = None,
    status: dict | None = None,
    status_error: str | None = None,
) -> str:
    decision_log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    track = baseline.get("track", "release")
    lines = [
        "# Upstream review report",
        "",
        f"- Upstream: `{baseline['repo']}` (`{baseline['branch']}`)",
        f"- Tracking: {track}",
        f"- Reviewed through: `{baseline['reviewed_through'][:7]}`"
        + (f" ({baseline['reviewed_release']})" if baseline.get("reviewed_release") else ""),
        f"- Last review date: {baseline['reviewed_date']}",
        "",
    ]
    if error:
        lines.extend(["## Check failed", "", f"```text\n{error}\n```", ""])
        return "\n".join(lines)
    if not commits:
        clean = (
            "No upstream release past the reviewed one. Nothing to review."
            if track == "release"
            else "No new upstream commits. Nothing to review."
        )
        lines.extend(["## Result", "", clean, ""])
        lines.extend(render_fork_status(status, status_error))
        return "\n".join(lines)

    headline = (
        f"Upstream released {release}: {len(commits)} commit(s) require review."
        if track == "release" and release
        else f"{len(commits)} upstream commit(s) require review."
    )
    lines.extend(
        [
            "## Result",
            "",
            headline,
            "",
            "| Commit | Date | Subject | Files |",
            "| --- | --- | --- | --- |",
        ]
    )
    for commit in commits:
        subject = commit["subject"].replace("|", "\\|")
        files = "<br>".join(item.replace("|", "\\|") for item in commit["files"][:8])
        if len(commit["files"]) > 8:
            files += f"<br>… +{len(commit['files']) - 8} more"
        lines.append(
            f"| `{commit['short']}` | {commit['date']} | {subject} | {files or '(none)'} |"
        )
    lines.extend(
        [
            "",
            f"Review each commit, record adopt/skip decisions in `{decision_log}`,",
            f"then advance `{BASELINE_PATH.parent.name}/upstream_baseline.json` only "
            "after verification.",
            "",
        ]
    )
    lines.extend(render_fork_status(status, status_error))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="upstream-review-report.md")
    parser.add_argument("--repo-dir", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when new commits require review.",
    )
    args = parser.parse_args()

    baseline: dict
    commits: list[dict] = []
    prs: list[dict] | None = None
    issues: list[dict] | None = None
    error: str | None = None
    release: str | None = None
    try:
        baseline = load_baseline()
        # Tickets are collected whatever the commit axis reports. This fork
        # tracks release tags, so between two releases the commit axis is
        # legitimately empty -- and that is exactly when an open pull request or
        # an issue is the only place upstream work is visible. Collecting them
        # only when a new tag exists would keep those months invisible.
        prs = collect_new_tickets(baseline, "pr")
        issues = collect_new_tickets(baseline, "issue")
        if baseline.get("track", "release") == "release":
            newest = latest_upstream_release(baseline, args.repo_dir)
            if newest is None:
                raise UpstreamCheckError("upstream publishes no semver tags to track")
            tag, sha = newest
            if sha != baseline["reviewed_through"]:
                release = tag
                ref = fetch_upstream_release(baseline, args.repo_dir, tag)
                commits = collect_new_commits(baseline, args.repo_dir, ref)
        else:
            ref = fetch_upstream(baseline, args.repo_dir)
            commits = collect_new_commits(baseline, args.repo_dir, ref)
    except UpstreamCheckError as exc:
        error = str(exc)
        baseline = {
            "repo": "unknown",
            "branch": "unknown",
            "reviewed_through": "0" * 40,
            "reviewed_date": "unknown",
        }

    status: dict | None = None
    status_error: str | None = None
    if error is None:
        # Informational only: a fork-status failure must not turn the review
        # check red, because it says nothing about whether upstream moved.
        try:
            status = fork_status(
                baseline, args.repo_dir, fetch_upstream(baseline, args.repo_dir)
            )
        except UpstreamCheckError as exc:
            status_error = str(exc)

    report = render_markdown(baseline, commits, error, release, status, status_error)
    if not error:
        report = append_ticket_sections(report, baseline, prs, issues)
    output = Path(args.output)
    output.write_text(report, encoding="utf-8")
    print(report)

    if error:
        return 2
    unavailable = [
        name
        for name, value in (("pull requests", prs), ("issues", issues))
        if value is None
    ]
    if unavailable:
        # Fail closed. A report that could not enumerate tickets must not
        # be allowed to read as a clean bill of health.
        print(
            "ERROR: gh could not enumerate upstream "
            + " and ".join(unavailable)
            + "."
        )
        return 2
    if args.strict and (commits or prs or issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



