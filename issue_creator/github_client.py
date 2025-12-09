import subprocess
import re
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
) -> Union[bool, "Issue", str, None]:
    """
    Create a GitHub issue.

    Returns:
      - PyGithub Issue object on success when using PyGithub
      - issue URL (string) on success when using gh CLI and URL can be parsed
      - True on success when using gh CLI but no URL parsed
      - False or None on failure
    """
    # Try PyGithub path if repo_obj is provided (preferred for programmatic access)
    if repo_obj is not None and Github is not None:
        try:
            # Normalize assignees into either None or a list[str] with no empty values
            normalized_assignees = None
            if assignees:
                if isinstance(assignees, (list, tuple)):
                    normalized_assignees = [str(a).strip() for a in assignees if a is not None and str(a).strip() != ""]
                else:
                    # single scalar value
                    normalized_assignees = [str(assignees).strip()] if str(assignees).strip() != "" else None
                if normalized_assignees == []:
                    normalized_assignees = None

            print(f"Attempting PyGithub create_issue: title={title!r}, assignees={normalized_assignees}, labels={labels}")
            issue = repo_obj.create_issue(
                title=title,
                body=body,
                assignees=normalized_assignees,
                labels=list(labels) if labels else None,
            )
            print(f"Created issue via PyGithub: {title} (#{issue.number})")
            return issue
        except Exception:
            # Print full traceback for debugging
            import traceback
            print("Failed to create issue via PyGithub (traceback follows):")
            traceback.print_exc()
            # fall through to CLI fallback

    # Fallback: use gh CLI (keeps previous behavior)
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if auth_check.returncode != 0:
        print("gh CLI not authenticated. Ensure 'gh auth login --with-token' was run.")
        return False

    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    if assignees:
        # ensure assignees passed to gh are comma-separated string
        if isinstance(assignees, (list, tuple)):
            assignee_arg = ",".join([str(a).strip() for a in assignees if a is not None and str(a).strip() != ""])
        else:
            assignee_arg = str(assignees).strip()
        if assignee_arg:
            cmd += ["--assignee", assignee_arg]
    if labels:
        for label in labels:
            cmd += ["--label", label]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = result.stdout.strip()
        print(f"Created issue via gh: {title}")
        print(stdout)
        # Attempt to parse an issue URL from stdout
        m = re.search(r"https?://github\.com/[^\s]+/issues/\d+", stdout)
        if m:
            return m.group(0)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Failed to create issue via gh CLI: {title}")
        print(exc.stderr.strip())
        return False
