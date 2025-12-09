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

def upload_attachment_to_repo_and_comment(repo, issue, filepath, jira_key):
    """
    Upload a local file to a dedicated attachments branch and post a comment with the raw URL.

    Behavior:
      - branch: issue-attachments/<jira_key>
      - file path on that branch: attachments/<jira_key>/<filename>
      - after upload, posts a comment on the issue embedding the image via raw.githubusercontent.com
    Returns True on success, False on failure (but never raises).
    """
    import time
    from github import GithubException

    filename = os.path.basename(filepath)
    branch_name = f"issue-attachments/{jira_key}"
    target_path = f"attachments/{jira_key}/{filename}"

    try:
        # 1) Ensure branch exists; if not, create it from default branch
        try:
            repo.get_branch(branch_name)
            print(f"Branch {branch_name} already exists.")
        except GithubException as exc:
            if getattr(exc, "status", None) == 404:
                print(f"Creating branch {branch_name} from default branch '{repo.default_branch}'")
                default_branch = repo.get_branch(repo.default_branch)
                sha = default_branch.commit.sha
                ref = f"refs/heads/{branch_name}"
                try:
                    repo.create_git_ref(ref, sha)
                    print(f"Created branch {branch_name}")
                    # give GitHub a moment to settle the new ref
                    time.sleep(1)
                except Exception as e_ref:
                    print(f"Failed to create branch {branch_name}: {e_ref}")
                    raise
            else:
                print(f"Error checking branch {branch_name}: {exc}")
                raise

        # 2) Read local file bytes
        try:
            with open(filepath, "rb") as fh:
                content_bytes = fh.read()
            # PyGithub create_file/update_file expects a string for content; decode latin-1 preserves bytes
            content_str = content_bytes.decode("latin-1")
        except Exception as e_read:
            print(f"Failed to read {filepath}: {e_read}")
            try:
                issue.create_comment(f"**Attachment failed to read:** `{filename}` — saved on runner at `{filepath}` (read error: {e_read})")
            except Exception:
                pass
            return False

        # 3) Create or update file on the attachments branch
        try:
            try:
                existing_file = repo.get_contents(target_path, ref=branch_name)
                # update existing file
                commit_msg = f"Update attachment {filename} for issue {issue.number}"
                repo.update_file(existing_file.path, commit_msg, content_str, existing_file.sha, branch=branch_name)
                print(f"Updated existing file at {target_path} on branch {branch_name}")
            except GithubException as not_found_exc:
                if getattr(not_found_exc, "status", None) == 404:
                    # create new file
                    commit_msg = f"Add attachment {filename} for issue {issue.number}"
                    repo.create_file(target_path, commit_msg, content_str, branch=branch_name)
                    print(f"Created file at {target_path} on branch {branch_name}")
                else:
                    print(f"Error checking/creating file {target_path}: {not_found_exc}")
                    raise
        except Exception as e_create:
            print(f"Failed to create/update file {target_path} on branch {branch_name}: {e_create}")
            try:
                issue.create_comment(f"**Attachment:** `{filename}` (failed to upload to repo: {e_create}). Local path: `{filepath}`")
            except Exception:
                pass
            return False

        # 4) Build raw URL and post comment with embedded image
        raw_url = f"https://raw.githubusercontent.com/{repo.full_name}/{branch_name}/{target_path}"
        comment_body = f"**Attachment:** `{filename}`\n\n![{filename}]({raw_url})"
        try:
            issue.create_comment(comment_body)
            print(f"Posted comment with attachment {filename} linking to {raw_url}")
            return True
        except Exception as e_comment:
            print(f"Failed to post comment for {filename}: {e_comment}")
            return False

    except Exception as exc_outer:
        print(f"Unexpected error uploading attachment {filepath}: {exc_outer}")
        try:
            issue.create_comment(f"**Attachment:** `{filename}` (unexpected failure: {exc_outer})")
        except Exception:
            pass
        return False

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
                    upload_attachment_to_repo_and_comment(repo, issue_obj, filepath, jira_issue_key)
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
