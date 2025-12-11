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

def upload_attachment(repo, issue, filepath, jira_key):
    """
    Upload a file to a single 'issue-attachments' branch under:
        attachments/<jira_key>/<filename>
    Tries PyGithub first → falls back to GitHub REST API.
    Always comments on the issue with the raw GitHub URL.
    """
    import time
    from github import GithubException
    import base64, os, requests

    branch_name = ATTACHMENTS_BRANCH
    filename = os.path.basename(filepath)
    target_path = f"attachments/{jira_key}/{filename}"

    # ----------------------------------------------------
    # STEP 1 — Ensure branch exists
    # ----------------------------------------------------
    try:
        repo.get_branch(branch_name)
    except GithubException as exc:
        if exc.status == 404:
            default = repo.get_branch(repo.default_branch)
            repo.create_git_ref(f"refs/heads/{branch_name}", default.commit.sha)
            time.sleep(1)
        else:
            return _comment_failure(issue, filename, f"Branch check failed: {exc}")

    # ----------------------------------------------------
    # STEP 2 — Read file contents
    # ----------------------------------------------------
    try:
        with open(filepath, "rb") as fh:
            raw_bytes = fh.read()
        content_str = raw_bytes.decode("latin-1")
    except Exception as e:
        return _comment_failure(issue, filename, f"File read failed: {e}")

    # ----------------------------------------------------
    # STEP 3 — Try PyGithub upload (preferred)
    # ----------------------------------------------------
    try:
        try:
            existing = repo.get_contents(target_path, ref=branch_name)
            repo.update_file(existing.path,
                             f"Update attachment {filename}",
                             content_str,
                             existing.sha,
                             branch=branch_name)
        except GithubException as nf:
            if nf.status == 404:
                repo.create_file(target_path,
                                 f"Add attachment {filename}",
                                 content_str,
                                 branch=branch_name)
            else:
                raise
        raw_url = f"https://raw.githubusercontent.com/{repo.full_name}/{branch_name}/{target_path}"
        issue.create_comment(f"**Attachment:** `{filename}`\n\n![{filename}]({raw_url})")
        return True

    except Exception as pyg_exc:
        print(f"[PyGithub failed] {pyg_exc}")

    # ----------------------------------------------------
    # STEP 4 — REST API fallback
    # ----------------------------------------------------
    token = os.getenv("GH_PAT_AGENT")
    if not token:
        return _comment_failure(issue, filename, "Missing GH_PAT_AGENT token")

    api_base = f"https://api.github.com/repos/{repo.full_name}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 4a — Ensure branch exists
    repo_info = requests.get(api_base, headers=headers).json()
    default_branch = repo_info.get("default_branch")

    ref_info = requests.get(f"{api_base}/git/refs/heads/{default_branch}",
                            headers=headers).json()
    sha = ref_info["object"]["sha"]

    requests.post(f"{api_base}/git/refs",
                  headers=headers,
                  json={"ref": f"refs/heads/{branch_name}", "sha": sha})

    # 4b — Upload file using REST /contents/{path}
    b64 = base64.b64encode(raw_bytes).decode()
    resp = requests.put(f"{api_base}/contents/{target_path}",
                        headers=headers,
                        json={
                            "message": f"Add attachment {filename}",
                            "content": b64,
                            "branch": branch_name
                        })

    if resp.status_code not in (200, 201):
        return _comment_failure(issue, filename, f"REST upload failed: {resp.text}")

    # SUCCESS
    raw_url = f"https://raw.githubusercontent.com/{repo.full_name}/{branch_name}/{target_path}"
    issue.create_comment(f"**Attachment:** `{filename}`\n\n![{filename}]({raw_url})")
    return True

def _comment_failure(issue, filename, msg):
    try:
        issue.create_comment(f"**Attachment failed:** `{filename}` — {msg}")
    except Exception:
        pass
    return False
    
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
    labels = ["jira-issue"]
    
    body = render_issue_from_jira(
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary,
        jira_description=jira_description
    )
    
    # robustly discover attachments (search runner workspace + cwd)
    def find_attachment_files():
        gw = os.getenv("GITHUB_WORKSPACE")
        cwd = os.getcwd()
        candidates = []
        if gw:
            candidates.append(os.path.join(gw, "attachments"))
        candidates.append(os.path.join(cwd, "attachments"))
        candidates.append("attachments")
        if gw:
            candidates.append(gw)
        checked = []
        found = []
        for p in candidates:
            if not p or p in checked:
                continue
            checked.append(p)
            print(f"DEBUG: checking path {p}")
            if os.path.isdir(p):
                matches = glob.glob(os.path.join(p, "**", "*"), recursive=True)
                files = [m for m in matches if os.path.isfile(m)]
                print(f"DEBUG: found {len(files)} files under {p}: {[os.path.basename(f) for f in files]}")
                found.extend(files)
            else:
                print(f"DEBUG: path {p} not present")
        # dedupe
        unique = []
        seen = set()
        for f in found:
            if f not in seen:
                unique.append(f)
                seen.add(f)
        return unique

    downloaded = []
    # prefer explicit JIRA_ATTACHMENTS parsing if provided (keeps existing behavior)
    if jira_attachments:
        body += "\n\n## 📎 Attachments from Jira\n"
        for attach in jira_attachments.split(","):
            if ":" in attach:
                filename = attach.split(":")[0]
                # try to map filename to local file
                candidates = find_attachment_files()
                for c in candidates:
                    if os.path.basename(c) == filename:
                        downloaded.append(c)
                        body += f"- 🖼️ `{filename}` (see comment below)\n"
                        break
    else:
        # auto-discover any files underneath attachments/
        downloaded = find_attachment_files()
        if downloaded:
            body += "\n\n## 📎 Attachments from Jira\n"
            for filepath in downloaded:
                filename = os.path.basename(filepath)
                body += f"- 🖼️ `{filename}` (see comment below)\n"
    
    # Create the issue (pass repo to get an Issue object when possible)
    created = create_issue_with_gh(
        title=title,
        body=body,
        assignees=assignees,
        labels=labels,
        gh_token=token,
        repo_obj=repo,
    )

    # Normalize to an Issue object when possible
    issue_obj = None
    if created and hasattr(created, "number"):
        issue_obj = created
    elif isinstance(created, str):
        # parse issue number from returned URL and fetch via PyGithub
        try:
            import re
            m = re.search(r"/issues/(\d+)", created)
            if m:
                issue_number = int(m.group(1))
                try:
                    issue_obj = repo.get_issue(issue_number)
                except Exception as exc:
                    print(f"Warning: could not fetch issue #{issue_number} via PyGithub: {exc}")
        except Exception as exc:
            print(f"Warning parsing issue URL returned by gh CLI: {exc}")

    if created:
        if issue_obj:
            print(f"\nSuccessfully created issue for {jira_issue_key} (#{issue_obj.number})")
        else:
            print(f"\nSuccessfully created issue for {jira_issue_key} (created via gh CLI)")
        # Attach files if we have any and an Issue object
        if downloaded:
            if issue_obj:
                print(f"Attaching {len(downloaded)} file(s) to issue #{issue_obj.number}")
                for filepath in downloaded:
                    upload_attachment(repo, issue_obj, filepath, jira_issue_key)
            else:
                print("Issue created via CLI and no PyGithub Issue object available; attachments cannot be uploaded programmatically in this run.")
    else:
        print(f"\n❌ Failed to create issue for {jira_issue_key}")
        sys.exit(1)

def main():
    args = parse_args()
    
    if args.from_jira:
        create_issue_from_jira()
        return

if __name__ == "__main__":
    main()
