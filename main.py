#!/usr/bin/env python3
import argparse
import os
import sys
import glob
import time
import requests
import base64
import json
from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException
from issue_creator.issue_renderer import render_issue_from_jira
from issue_creator.github_client import build_issue_labels, create_issue_with_gh

# Use a single attachments branch for all issues; each issue will have its own folder under attachments/
ATTACHMENTS_BRANCH = os.getenv("ATTACHMENTS_BRANCH", "issue-attachments").strip()
target_instance = os.getenv("TARGET_INSTANCE", "brand_landscape_analyzer").strip().lower()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a single GitHub issue from Jira environment variables (Jira-driven workflow)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print issues without creating them")
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
    
def create_issue_from_jira():
    """Create a GitHub issue from Jira environment variables."""
    load_dotenv()
    
    jira_issue_key = os.getenv("JIRA_ISSUE_KEY")
    jira_summary = os.getenv("JIRA_SUMMARY")
    jira_attachments = os.getenv("JIRA_ATTACHMENTS", "")
    jira_description = os.getenv("JIRA_DESCRIPTION", "")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    # labels = os.getenv("LABEL")
    
    if not jira_issue_key:
        print("Error: JIRA_ISSUE_KEY environment variable not set")
        sys.exit(1)
    if not jira_summary:
        print("Error: JIRA_SUMMARY environment variable not set")
        sys.exit(1)
    
    title = f"{jira_summary} - {jira_issue_key}"
    
    if dry_run:
        print("\n=== DRY RUN MODE ===")
        print(f"Would create issue:")
        print(f"  Title: {title}")
        print(f"  Jira Key: {jira_issue_key}")
        print(f"  Summary: {jira_summary}")
        return
    
    token = os.getenv("GH_PAT_AGENT")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    print("GH_PAT_AGENT environment variable value "+ token)
    print("GITHUB_REPOSITORY environment variable value "+ repo_name)
    
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
    # assignees = ["hrutvipujar-sudo"] 
    labels = ["jira-auto-fix"]
    
    body = render_issue_from_jira(
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary,
        jira_description=jira_description
    )
    
    # Create the issue (pass repo to get an Issue object when possible)
    created = create_issue_with_gh(
        title=title,
        body=body,
        assignees=assignees,
        labels=labels,
        gh_token=token,
        repo_obj=repo,
    )


def main():
    args = parse_args()
    
    if args.from_jira:
        create_issue_from_jira()
        return

if __name__ == "__main__":
    main()
