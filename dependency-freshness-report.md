# Dependency freshness report

## Python packages (PyPI)

| Package | Declared in | Requirement | Latest | Status |
| --- | --- | --- | --- | --- |
| `pytest` | `pyproject.toml` | `pytest>=9.1.1` | `9.1.1` | OK |
| `PyYAML` | `pyproject.toml` | `PyYAML>=6.0` | `6.0.3` | OK |

## GitHub Actions (pinned in .github/workflows/)

| Package | Declared in | Requirement | Latest | Status |
| --- | --- | --- | --- | --- |
| `actions/checkout` | `codeql.yml, dependency-freshness.yml, release.yml, reusable-policy-check.yml, self-test.yml, upstream-check.yml` | `actions/checkout@v7.0.1` | `7.0.1` | OK |
| `actions/download-artifact` | `release.yml` | `actions/download-artifact@v8.0.2` | `8.0.2` | OK |
| `actions/setup-python` | `dependency-freshness.yml, release.yml, reusable-policy-check.yml, self-test.yml, upstream-check.yml` | `actions/setup-python@v7.1.0` | `7.1.0` | OK |
| `actions/upload-artifact` | `release.yml` | `actions/upload-artifact@v7.0.2` | `7.0.2` | OK |
| `github/codeql-action/analyze` | `codeql.yml` | `github/codeql-action/analyze@v4.39.1` | `4.39.1` | OK |
| `github/codeql-action/init` | `codeql.yml` | `github/codeql-action/init@v4.39.1` | `4.39.1` | OK |

Declared floors are compared with the current release at the precision each
declaration states. The installed environment is not inspected and no file is
edited by this check.

## Review policy

1. Read the release notes, then run the repository gate before raising anything.
2. Repin a GitHub Action by its new commit SHA with a `# vX.Y.Z` comment; do not
   switch a pinned SHA back to a floating tag.
3. Raising a floor only to silence this report is not an exit: a declaration is a
   compatibility promise. When the floor really must stay, record why:
   `# freshness-hold: <why>` on the declaring line for a standing policy, or an
   entry in `.github/dependency-deferrals.json` with `deferredLatest` for
   "reviewed, not now" (it expires once the registry passes that release).
