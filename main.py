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

def create_branch_and_upload_via_api(token: str, owner: str, repo_name: str, jira_key: str, local_filepath: str, branch_name: str = None) -> bool:
    """
    REST fallback: create a single attachments branch (default 'issue-attachments') from default branch and upload
    local_filepath into attachments/<jira_key>/<filename> on that branch using GitHub REST API.
    Returns True on success.
    """
    if branch_name is None:
        branch_name = ATTACHMENTS_BRANCH
    api_base = f"https://api.github.com/repos/{owner}/{repo_name}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "attachments-uploader"
    }

    # 1) Get default branch name and sha
    r = requests.get(f"{api_base}", headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"[REST fallback] Failed to get repo info: {r.status_code} {r.text}")
        return False
    repo_info = r.json()
    default_branch = repo_info.get("default_branch")
    print(f"[REST fallback] default_branch: {default_branch}")

    r = requests.get(f"{api_base}/git/refs/heads/{default_branch}", headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"[REST fallback] Failed to get ref for {default_branch}: {r.status_code} {r.text}")
        return False
    base_sha = r.json()["object"]["sha"]
    print(f"[REST fallback] base_sha: {base_sha}")

    # 2) Create the attachments branch ref (if it doesn't already exist)
    payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
    r = requests.post(f"{api_base}/git/refs", headers=headers, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        # if branch already exists, that's fine
        if r.status_code == 422 and "Reference already exists" in r.text:
            print(f"[REST fallback] Branch {branch_name} already exists (api message).")
        else:
            print(f"[REST fallback] Failed to create ref {branch_name}: {r.status_code} {r.text}")
            return False
    else:
        print(f"[REST fallback] Created branch {branch_name} via API")

    # 3) Upload file to contents endpoint under attachments/<jira_key>/<filename>
    filename = os.path.basename(local_filepath)
    target_path = f"attachments/{jira_key}/{filename}"
    try:
        with open(local_filepath, "rb") as fh:
            content_bytes = fh.read()
    except Exception as e:
        print(f"[REST fallback] Failed to read {local_filepath}: {e}")
        return False

    b64 = base64.b64encode(content_bytes).decode("ascii")
    payload = {
        "message": f"Add attachment {filename} for Jira {jira_key}",
        "content": b64,
        "branch": branch_name
    }
    r = requests.put(f"{api_base}/contents/{target_path}", headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        print(f"[REST fallback] Uploaded {target_path} to branch {branch_name}")
        return True
    else:
        # If file exists, response will contain current sha — you can update by sending that sha.
        print(f"[REST fallback] Failed to upload {target_path}: {r.status_code} {r.text}")
        return False

def upload_attachment_to_repo_and_comment(repo, issue, filepath, jira_key):
    """
    Upload a local file to a single attachments branch and post a comment with the raw URL.

    Behavior:
      - single branch: ATTACHMENTS_BRANCH (default 'issue-attachments')
      - file path on that branch: attachments/<jira_key>/<filename>
      - after upload, posts a comment on the issue embedding the image via raw.githubusercontent.com
    Returns True on success, False on failure (but never raises).
    """
    import time
    from github import GithubException

    filename = os.path.basename(filepath)
    branch_name = ATTACHMENTS_BRANCH
    target_path = f"attachments/{jira_key}/{filename}"

    try:
        # 1) Ensure attachments branch exists; if not, create it from default branch
        try:
            repo.get_branch(branch_name)
            print(f"Branch {branch_name} already exists.")
        except GithubException as exc:
            # If branch not found, attempt to create it from default branch
            if getattr(exc, "status", None) == 404:
                print(f"Branch {branch_name} not found; attempting to create it from default branch '{repo.default_branch}'")
                # fetch the default branch to get SHA
                try:
                    default_branch = repo.get_branch(repo.default_branch)
                except GithubException as exc_def:
                    print(f"Failed to fetch default branch '{repo.default_branch}': status={getattr(exc_def,'status',None)}, data={getattr(exc_def,'data',exc_def)}")
                    # cannot proceed without a valid base SHA
                    try:
                        issue.create_comment(f"**Attachment upload failed:** could not determine default branch '{repo.default_branch}' to create attachments branch.")
                    except Exception:
                        pass
                    return False
                try:
                    sha = default_branch.commit.sha
                    ref = f"refs/heads/{branch_name}"
                    try:
                        repo.create_git_ref(ref, sha)
                        print(f"Created branch {branch_name}")
                        # give GitHub a moment to settle the new ref
                        time.sleep(1)
                    except GithubException as e_ref:
                        # If another process created the ref between the get and create, treat as success
                        data = getattr(e_ref, "data", "")
                        message_text = ""
                        try:
                            if isinstance(data, dict):
                                message_text = data.get("message", "")
                            else:
                                message_text = str(data)
                        except Exception:
                            message_text = str(data)
                        if getattr(e_ref, "status", None) == 422 and ("Reference already exists" in message_text or "reference already exists" in message_text.lower()):
                            print(f"Branch {branch_name} appears to have been created concurrently (422). Continuing.")
                            # small pause then confirm existence
                            time.sleep(0.5)
                            try:
                                repo.get_branch(branch_name)
                            except Exception as confirm_exc:
                                print(f"Unable to confirm branch after concurrent-create: {confirm_exc}")
                                raise
                        else:
                            print(f"Failed to create branch {branch_name}: status={getattr(e_ref,'status',None)}, data={message_text}")
                            raise
                except Exception as e_ref_outer:
                    print(f"Failed to create attachments branch {branch_name}: {e_ref_outer}")
                    # Let outer handler run fallback behavior (it will attempt REST fallback)
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

        # 3) Create or update file on the attachments branch inside the per-issue folder
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
                    print(f"Error checking/creating file {target_path}: status={getattr(not_found_exc,'status',None)}, data={getattr(not_found_exc,'data',not_found_exc)}")
                    raise
        except Exception as e_create:
            print(f"Failed to create/update file {target_path} on branch {branch_name}: {e_create}")
            # --- REST fallback invocation ---
            token = os.getenv("GH_PAT_AGENT")
            owner_repo = repo.full_name.split("/", 1)
            if token and len(owner_repo) == 2:
                owner, repo_name = owner_repo
                print("[fallback] Attempting REST fallback to create branch & upload file")
                ok = create_branch_and_upload_via_api(token, owner, repo_name, jira_key, filepath, branch_name=branch_name)
                if ok:
                    raw_url = f"https://raw.githubusercontent.com/{repo.full_name}/{branch_name}/{target_path}"
                    try:
                        # Make fallback visible in the comment so it's obvious how the file was uploaded
                        issue.create_comment(f"**Attachment:** `{filename}` (uploaded via REST fallback)\n\n![{filename}]({raw_url})")
                        print(f"Posted comment with attachment {filename} linking to {raw_url} (REST fallback)")
                        return True
                    except Exception as e_comment:
                        print(f"Failed to post comment after REST fallback upload: {e_comment}")
                        return False
            # --- end REST fallback ---
            # fallback: post comment with local path so humans can retrieve it
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
    jira_summary = os.getenv("JIRA_SUMMARY", "")
    jira_attachments = os.getenv("JIRA_ATTACHMENTS", "")
    jira_description = os.getenv("JIRA_DESCRIPTION", "")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    # labels = os.getenv("LABEL")
    
    if not jira_issue_key:
        print("Error: JIRA_ISSUE_KEY environment variable not set")
        sys.exit(1)
    
    # Use jira_summary if provided, otherwise use a default title
    title = f"{jira_summary} - {jira_issue_key}" if jira_summary else f"Issue {jira_issue_key}"
    
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

if __name__ == "__main__":
    main()
