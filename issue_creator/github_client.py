import subprocess
from typing import List, Sequence
import pandas as pd

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

def create_issue_with_gh(title: str, body: str, assignees, labels=None):
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