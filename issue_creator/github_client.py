import os
import subprocess
from typing import List, Sequence, Optional, Union
import pandas as pd

# Optional import for PyGithub usage
try:
    from github import Github
    from github.Issue import Issue
except Exception:
    Github = None
    Issue = None


def severity_label(cvss_raw) -> str:
    try:
        score = float(cvss_raw) if cvss_raw not in ("N/A", None, "") else 0.0
    except (TypeError, ValueError):
        score = 0.0
    if score >= 9.0:
        return "severity:critical"
    if score >= 7.0:
        return "severity:high"
    if score >= 4.0:
        return "severity:medium"
    return "severity:low"

def build_issue_labels(vuln: pd.Series, extra_labels: Sequence[str]) -> List[str]:
    labels: List[str] = list(extra_labels) if extra_labels else []
    labels.append("vulnerability")
    labels.append(severity_label(vuln.get("CVSS Score")))
    seen = set()
    deduped: List[str] = []
    for label in labels:
        if label and label not in seen:
            deduped.append(label)
            seen.add(label)
    return deduped

def create_issue_with_gh(
    title: str,
    body: str,
    assignees,
    labels: Optional[Sequence[str]] = None,
    gh_token: Optional[str] = None,
    repo_obj: Optional[object] = None,
) -> Union[bool, "Issue", None]:
    """
    Create a GitHub issue.

    Behavior:
    - If a PyGithub Repo object is passed in `repo_obj` (and PyGithub is available),
      use that to create the issue and return the created Issue object.
    - Otherwise, fall back to using the `gh` CLI. The CLI path returns True on success,
      False on failure (maintains backward compatibility).

    Returns:
      - PyGithub Issue object on success when using PyGithub
      - True on success when using gh CLI
      - False or None on failure
    """
    # Try PyGithub path if repo_obj is provided (preferred for programmatic access)
    if repo_obj is not None and Github is not None:
        try:
            # repo_obj is assumed to be a PyGithub Repository object
            issue = repo_obj.create_issue(
                title=title,
                body=body,
                assignees=assignees or None,
                labels=list(labels) if labels else None,
            )
            print(f"Created issue via PyGithub: {title} (#{issue.number})")
            return issue
        except Exception as exc:
            print(f"Failed to create issue via PyGithub: {exc}")
            # fall through to CLI fallback

    # Fallback: use gh CLI (keeps previous behavior)
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if auth_check.returncode != 0:
        print("gh CLI not authenticated. Ensure 'gh auth login --with-token' was run.")
        return False
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    if assignees:
        cmd += ["--assignee", ",".join(assignees)]
    if labels:
        for label in labels:
            cmd += ["--label", label]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Created issue via gh: {title}")
        print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Failed to create issue via gh CLI: {title}")
        print(exc.stderr.strip())
        return False
