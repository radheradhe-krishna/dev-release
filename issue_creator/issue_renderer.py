from pathlib import Path
from .utils import SafeDict, sanitize

_TEMPLATE_CACHE: str | None = None
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "issue_prompt.md"
JIRA_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "jira_issue_prompt.md"

def get_issue_template() -> str:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        _TEMPLATE_CACHE = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _TEMPLATE_CACHE

def render_issue(vuln):
    context = SafeDict(
        scan_type=sanitize(vuln.get("Scan Type")),
        vuln_id=sanitize(vuln.get("ID")),
        name=sanitize(vuln.get("Name")),
        cvss_score=sanitize(vuln.get("CVSS Score")),
        total_count=sanitize(vuln.get("Total Count")),
        finding_type=sanitize(vuln.get("Finding Type")),
        compliance=sanitize(vuln.get("Compliance Framework(s)")),
        teams_impacted=sanitize(vuln.get("Teams")),
        unique_instances=sanitize(vuln.get("Unique Instance List")),
        description=sanitize(vuln.get("Description", "No description provided")),
        recommendation=sanitize(vuln.get("Recommendation", "No recommendation provided")),
        exploit_available=sanitize(vuln.get("Exploit Available")),
        exploit_rating=sanitize(vuln.get("Exploit Rating")),
        mandi_ease=sanitize(vuln.get("Mandiant Ease of Attack")),
        exploit_consequence=sanitize(vuln.get("Exploit Consequence")),
        mitigation=sanitize(vuln.get("Mitigation")),
        zero_day=sanitize(vuln.get("Zero Day")),
        epss_score=sanitize(vuln.get("EPSS Score")),
        cisa_kev=sanitize(vuln.get("CISA KEV Vulnerability")),
    )

    return get_issue_template().format_map(context)

def render_issue_from_jira(jira_issue_key: str, jira_summary: str, jira_description: str) -> str:
    """Render issue body from Jira inputs."""
    template = """## Vulnerability Details (from Jira)
- **Jira Issue Key:** {jira_issue_key}
- **Summary:** {jira_summary}

## Description
This security issue was reported in Jira as **{jira_description}**.

**Summary:** {jira_summary}

**Description:** {jira_description}

Please investigate and resolve this vulnerability in the codebase.

## Recommendation
1. Review the code related to this Jira issue
2. Identify the root cause of the vulnerability
3. Implement appropriate fixes following security best practices
4. Add or update tests to prevent regression
5. Document any changes made

---

**Instructions for Copilot Coding Agent**
1. Search the repository for code related to the Jira issue: {jira_issue_key}
2. Confirm that the vulnerable code path exists in the repo.
3. If the finding is not reproducible, explain why in an issue comment and stop—do not create new files.
4. Review the affected components and identify the security vulnerability.
5. Update or patch the vulnerable code, modifying existing files only.
6. Add or update automated tests or scanners when a relevant test suite already exists; otherwise document the gap.
7. Keep code comments minimal—add them only when they clarify non-obvious logic.
8. Commit, create a branch, and open a PR referencing this issue.
9. In the PR description, reference the Jira issue: {jira_issue_key}
"""
    
    context = SafeDict(
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary,
    )
    
    return template.format_map(context)
