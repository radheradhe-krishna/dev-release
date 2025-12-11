from pathlib import Path
from .utils import SafeDict, sanitize

_TEMPLATE_CACHE: str | None = None
JIRA_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "jira_issue_prompt.md"

def render_issue_from_jira(jira_issue_key: str, jira_summary: str, jira_description: str) -> str:
    """Render an improved, bug-focused issue body from Jira inputs.

    This function requires the external template file at:
      issue_creator/templates/jira_issue_prompt.md

    The template is loaded and formatted with the sanitized inputs. If the file is
    missing this function will raise a FileNotFoundError so callers are aware the
    template must be present.
    """
    # sanitize inputs
    jira_issue_key = sanitize(jira_issue_key or "UNKNOWN")
    jira_summary = sanitize(jira_summary or "No summary provided")
    jira_description = sanitize(jira_description or "No description provided")

    context = SafeDict(
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary,
        jira_description=jira_description,
    )

    # Load external template (no fallback)
    return JIRA_TEMPLATE_PATH.read_text(encoding="utf-8").format_map(context)
