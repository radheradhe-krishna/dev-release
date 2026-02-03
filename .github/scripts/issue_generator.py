"""
Issue Body Generator
Handles formatting and template rendering for GitHub issues
"""
import subprocess
import re
from pathlib import Path
from typing import List, Sequence, Optional, Union

try:
    from github import Github
except ImportError:
    Github = None


class IssueBodyGenerator:
    """Generate GitHub issue body from Jira data"""
    
    def __init__(self, template_path=None):
        """Initialize with optional custom template path"""
        if template_path is None:
            # Default template in .github/templates/ directory
            template_path = Path(__file__).parent.parent / 'templates' / 'issue_template.md'
        
        self.template_path = Path(template_path)
        self.template_content = self._load_template()
    
    def _load_template(self):
        """Load template from file"""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"❌ ERROR: Template not found: {self.template_path}")
            print(f"   Please ensure the template file exists in the templates folder.")
            raise SystemExit(1)
    
    def generate(self, jira_data, config, attachments=None):
        """
        Generate issue body from Jira data
        
        Args:
            jira_data: Dictionary containing Jira issue data
            config: Configuration dictionary with JIRA_BASE_URL, etc.
            attachments: List of attachment dictionaries
        
        Returns:
            Formatted issue body string
        """
        fields = jira_data['fields']
        bug_key = jira_data['key']
        
        # Extract all fields
        bug_type = fields.get('issuetype', {}).get('name', 'Bug')
        summary = fields.get('summary', 'No title')
        priority = fields.get('priority', {}).get('name', 'Medium')
        status = fields.get('status', {}).get('name', 'Unknown')
        reporter = fields.get('reporter', {}).get('displayName', 'Unknown')
        
        # Handle assignee safely
        assignee_field = fields.get('assignee')
        assignee = assignee_field.get('displayName', 'Unassigned') if assignee_field else 'Unassigned'
        # assignee = ['copilot-swe-agent'];
        created = fields.get('created', 'Unknown')
        updated = fields.get('updated', 'Unknown')
        
        # Get description
        description = self._extract_description(fields.get('description', ''))
        
        # Build components
        components = [c['name'] for c in fields.get('components', [])]
        components_text = ', '.join(components) if components else 'None'
        
        # Build labels
        labels = fields.get('labels', [])
        labels_text = ', '.join(f'`{label}`' for label in labels) if labels else 'None'
        
        # Build versions
        affected_versions = [v['name'] for v in fields.get('versions', [])]
        versions_text = ', '.join(affected_versions) if affected_versions else 'Not specified'
        
        fix_versions = [v['name'] for v in fields.get('fixVersions', [])]
        fix_versions_text = ', '.join(fix_versions) if fix_versions else 'Not specified'
        
        # Get environment
        environment = self._extract_description(fields.get('environment', ''))
        if not environment:
            environment = 'Not specified'
        
        # Build attachments section
        attachments_section = self._build_attachments_section(attachments or [])
        
        # Build custom fields section
        custom_fields_section = self._build_custom_fields_section(fields)
        
        # Build Jira URL
        jira_url = f"{config['JIRA_BASE_URL']}/browse/{bug_key}"
        
        # Replace all placeholders
        issue_body = self.template_content.format(
            bug_type=bug_type,
            summary=summary,
            bug_key=bug_key,
            bug_key_lower=bug_key.lower(),
            jira_url=jira_url,
            priority=priority,
            status=status,
            reporter=reporter,
            assignee=assignee,
            components=components_text,
            labels=labels_text,
            versions=versions_text,
            fix_versions=fix_versions_text,
            description=description,
            environment=environment,
            attachments_section=attachments_section,
            custom_fields_section=custom_fields_section,
            created=created,
            updated=updated
        )
        
        return issue_body
    
    def _extract_description(self, desc_data):
        """Extract text from description (handles ADF format)"""
        if not desc_data:
            return 'No description provided'
        
        if isinstance(desc_data, str):
            return desc_data
        
        # Handle Atlassian Document Format (ADF)
        if isinstance(desc_data, dict):
            text_parts = []
            
            def extract_content(node):
                if isinstance(node, dict):
                    if node.get('type') == 'text':
                        text_parts.append(node.get('text', ''))
                    if 'content' in node:
                        for child in node['content']:
                            extract_content(child)
                elif isinstance(node, list):
                    for item in node:
                        extract_content(item)
            
            extract_content(desc_data)
            return '\n'.join(text_parts) if text_parts else 'No description provided'
        
        return str(desc_data)
    
    def _build_attachments_section(self, attachments):
        """Build formatted attachments section"""
        if not attachments:
            return ""
        
        section = "\n## 📎 Attachments\n\n"
        for att in attachments:
            size_kb = att['size'] / 1024
            file_icon = self._get_file_icon(att['filename'])
            
            if att.get('github_url'):
                section += f"- {file_icon} **[{att['filename']}]({att['github_url']})** - {size_kb:.2f} KB\n"
            else:
                section += f"- {file_icon} **{att['filename']}** - {size_kb:.2f} KB ⚠️ *Upload failed*\n"
        
        return section
    
    def _get_file_icon(self, filename):
        """Get emoji icon based on file extension"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        icons = {
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
            'pdf': '📄', 'doc': '📄', 'docx': '📄', 'txt': '📄',
            'zip': '📦', 'tar': '📦', 'gz': '📦', 'rar': '📦',
            'log': '📝', 'json': '📋', 'xml': '📋', 'yaml': '📋', 'yml': '📋',
            'mp4': '🎥', 'avi': '🎥', 'mov': '🎥',
            'mp3': '🎵', 'wav': '🎵',
        }
        return icons.get(ext, '📎')
    
    def _build_custom_fields_section(self, fields):
        """Build section for custom fields if they exist"""
        custom_fields = []
        
        # Look for common custom fields
        for key, value in fields.items():
            if key.startswith('customfield_') and value:
                # Try to extract meaningful data
                if isinstance(value, dict):
                    if 'value' in value:
                        custom_fields.append(f"- **{key}**: {value['value']}")
                    elif 'name' in value:
                        custom_fields.append(f"- **{key}**: {value['name']}")
                elif isinstance(value, list) and value:
                    items = ', '.join([
                        str(item.get('value', item)) if isinstance(item, dict) else str(item) 
                        for item in value
                    ])
                    custom_fields.append(f"- **{key}**: {items}")
                elif isinstance(value, (str, int, float, bool)):
                    custom_fields.append(f"- **{key}**: {value}")
        
        if custom_fields:
            return "\n## 🔧 Custom Fields\n\n" + '\n'.join(custom_fields) + "\n"
        return ""


# Standalone function to create GitHub issues
def create_issue_with_gh(
    title: str,
    body: str,
    assignees,
    labels: Optional[Sequence[str]] = None,
    gh_token: Optional[str] = None,
    repo_obj: Optional[object] = None,
) -> Union[bool, object, str, None]:
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
    
    # Add labels first (these usually work)
    if labels:
        for label in labels:
            cmd += ["--label", label]
    
    # Try to add assignees, but create issue without them if they don't exist
    assignee_arg = None
    if assignees:
        # ensure assignees passed to gh are comma-separated string
        if isinstance(assignees, (list, tuple)):
            assignee_arg = ",".join([str(a).strip() for a in assignees if a is not None and str(a).strip() != ""])
        else:
            assignee_arg = str(assignees).strip()
    
    try:
        # Try creating with assignees first
        if assignee_arg:
            cmd_with_assignees = cmd + ["--assignee", assignee_arg]
            result = subprocess.run(cmd_with_assignees, capture_output=True, text=True, check=True)
        else:
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
        # If assignment failed, try again without assignees
        if assignee_arg and "could not assign" in exc.stderr:
            print(f"⚠️  Warning: Could not assign to {assignee_arg}, creating issue without assignee...")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                stdout = result.stdout.strip()
                print(f"Created issue via gh: {title}")
                print(stdout)
                m = re.search(r"https?://github\.com/[^\s]+/issues/\d+", stdout)
                if m:
                    return m.group(0)
                return True
            except subprocess.CalledProcessError as retry_exc:
                print(f"Failed to create issue via gh CLI: {title}")
                print(retry_exc.stderr.strip())
                return False
        else:
            print(f"Failed to create issue via gh CLI: {title}")
            print(exc.stderr.strip())
            return False
