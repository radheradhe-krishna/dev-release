#!/usr/bin/env python3
import argparse
import os
import sys
import glob
from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException
from issue_creator.issue_loader import load_vulnerabilities
from issue_creator.issue_renderer import render_issue, render_issue_from_jira
from issue_creator.github_client import build_issue_labels, create_issue_with_gh

target_instance = os.getenv("TARGET_INSTANCE", "brand_landscape_analyzer").strip().lower()

def parse_args():
    parser = argparse.ArgumentParser(description="Create GitHub issues from vulnerability Excel file or Jira inputs")
    parser.add_argument("excel_file", nargs="?", default="vulnerabilities-issues.xlsx", help="Path to the Excel file")
    parser.add_argument("--dry-run", action="store_true", help="Print issues without creating them")
    parser.add_argument("--labels", nargs="*", help="Additional labels to add to issues")
    parser.add_argument("--from-jira", action="store_true", help="Create issue from Jira environment variables")
    return parser.parse_args()

def ensure_repo(token: str, repo_name: str):
    try:
        gh = Github(token)
        repo = gh.get_repo(repo_name)
        print(f"Connected to repository: {repo.full_name}")
        return gh, repo
    except Exception as exc:
        print(f"Error connecting to GitHub: {exc}")
        sys.exit(1)

def validate_assignees(repo, gh, assignees):
    valid, invalid = [], []
    for username in assignees:
        try:
            try:
                is_collab = repo.has_in_collaborators(username)
            except TypeError:
                user_obj = gh.get_user(username)
                is_collab = repo.has_in_collaborators(user_obj)
            (valid if is_collab else invalid).append(username)
        except GithubException as exc:
            print(f"GitHub error when checking assignee '{username}': status={getattr(exc, 'status', 'unknown')}, data={getattr(exc, 'data', exc)}")
            invalid.append(username)
        except Exception as exc:
            print(f"Unexpected error when checking assignee '{username}': {exc}")
            invalid.append(username)
    if valid:
        print(f"Will attempt to assign issues to: {valid}")
    if invalid:
        print(f"Warning: These assignees are not assignable and will be skipped: {invalid}")
    return valid

def upload_image_to_issue(repo, issue, image_path):
    """Upload image as an issue comment with embedded image"""
    filename = os.path.basename(image_path)
    
    # Read image and create comment with image
    # GitHub will host the image when you add it to a comment
    with open(image_path, 'rb') as f:
        # You can upload via issue.create_comment() with drag-drop simulation
        # Or use the simpler approach: reference local path and let GitHub handle it
        pass
    
    # Alternative: Upload to a release asset or gist and get URL
    # For now, we'll just reference the filename
    return filename
    
def create_issue_from_jira():
    """Create a GitHub issue from Jira environment variables."""
    load_dotenv()
    
    jira_issue_key = os.getenv("JIRA_ISSUE_KEY")
    jira_summary = os.getenv("JIRA_SUMMARY")
    jira_attachments = os.getenv("JIRA_ATTACHMENTS", "")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    # labels = os.getenv("LABEL")

    if not jira_issue_key:
        print("Error: JIRA_ISSUE_KEY environment variable not set")
        sys.exit(1)
    if not jira_summary:
        print("Error: JIRA_SUMMARY environment variable not set")
        sys.exit(1)
    
    title = f"[Security] {jira_summary} - {jira_issue_key}"
    
    if dry_run:
        print("\n=== DRY RUN MODE ===")
        print(f"Would create issue:")
        print(f"  Title: {title}")
        print(f"  Jira Key: {jira_issue_key}")
        print(f"  Summary: {jira_summary}")
        return
    
    token = os.getenv("GH_PAT_AGENT")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    
    if not token:
        print("Error: GH_PAT_AGENT environment variable not set")
        sys.exit(1)
    if not repo_name:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        sys.exit(1)
    
    gh, repo = ensure_repo(token, repo_name)
    assignees_env = os.getenv("ASSIGNEES", "").strip()
    assignees = [part.strip() for part in assignees_env.split(",") if part.strip()]
    
    # Default label for vulnerability
    labels = ["jira-issue"]
    
    body = render_issue_from_jira(
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary
    )
    
    # Add attachment section if attachments exist
    attachment_files = []
    downloaded = []
    if jira_attachments:
        body += "\n\n## 📎 Attachments from Jira\n"
        
        # Parse attachment filenames
        for attach in jira_attachments.split(","):
            if ":" in attach:
                filename = attach.split(":")[0]
                attachment_files.append(filename)
        
        # List downloaded files
        downloaded = glob.glob("attachments/*")
        for filepath in downloaded:
            filename = os.path.basename(filepath)
            body += f"- 🖼️ `{filename}` (see comment below)\n"
    
    # Create the issue
    created = create_issue_with_gh(
        title=title,
        body=body,
        assignees=assignees,
        labels=labels,
    )

    if created:
        print(f"\nSuccessfully created issue for {jira_issue_key}")

        # If attachments exist, add them as comments
        if jira_attachments and downloaded:
            try:
                # Try to find the created issue by title among open issues
                issue = None
                for i in repo.get_issues(state='open'):
                    if i.title == title:
                        issue = i
                        break
                # Fallback to the most recently opened issue if we didn't find a title match
                if issue is None:
                    issues = list(repo.get_issues(state='open'))
                    issue = issues[0] if issues else None

                if issue:
                    for filepath in downloaded:
                        filename = os.path.basename(filepath)
                        comment_body = f"**Attachment:** `{filename}`\n\n"
                        comment_body += f"_Downloaded from Jira. File saved at: `{filepath}`_"
                        issue.create_comment(comment_body)
                else:
                    print("Warning: could not find the newly created issue to attach files as comments.")
            except Exception as exc:
                print(f"Warning: failed to add attachment comments: {exc}")
    else:
        print(f"\n❌ Failed to create issue for {jira_issue_key}")
        sys.exit(1)

def main():
    args = parse_args()
    
    if args.from_jira:
        create_issue_from_jira()
        return
    
    load_dotenv()
    df = load_vulnerabilities(args.excel_file)
    print(df.columns.tolist())

    if args.dry_run:
        print("\n=== DRY RUN MODE ===")
        print(f"Would create {len(df)} issues:")
        for _, vuln in df.iterrows():
            instances = vuln.get("Unique Instance List", "")
            if "brand_landscape_analyzer" not in str(instances):
                continue
            title = f"[Security] {vuln.get('Name', 'Vulnerability')} - {vuln.get('ID', 'Unknown ID')}"
            print(f"  - {title}")
            print(f"    CVSS Score: {vuln.get('CVSS Score', 'N/A')}")
            print(f"    Finding Type: {vuln.get('Finding Type', 'N/A')}")
            print()
        return

    token = os.getenv("GH_PAT_AGENT")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    if not token:
        print("Error: GH_PAT_AGENT environment variable not set")
        sys.exit(1)
    if not repo_name:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        sys.exit(1)

    gh, repo = ensure_repo(token, repo_name)
    assignees_env = os.getenv("ASSIGNEES", "").strip()
    assignees = [part.strip() for part in assignees_env.split(",") if part.strip()]

    created = 0
    for idx, vuln in df.iterrows():
        instances = str(vuln.get("Unique Instance List", "")).lower()
        if target_instance not in instances:
            continue
        print(f"Processing vulnerability {idx + 1}/{len(df)}: {vuln.get('Name', 'Vulnerability')} - {vuln.get('ID', 'Unknown ID')} [Label: {vuln.get('Label', 'N/A')}]")
        labels = build_issue_labels(vuln, args.labels or [])
        if create_issue_with_gh(
            title=f"[Security] {vuln.get('Name', 'Vulnerability')} - {vuln.get('ID', 'Unknown ID')}",
            body=render_issue(vuln),
            assignees=assignees,
            labels=labels,
        ):
            created += 1

    print(f"\nSuccessfully created {created} issues out of {len(df)} vulnerabilities")

if __name__ == "__main__":
    main()
