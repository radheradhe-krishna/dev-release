#!/usr/bin/env python3
"""
Upload local files from ATTACHMENTS_DIR into a single repo branch (ATTACHMENTS_BRANCH)
under attachments/<JIRA_ISSUE_KEY>/, then post a GitHub issue comment embedding the raw URLs.

Requires:
  - environment variables:
      GITHUB_REPOSITORY (owner/repo)
      GH_PAT_AGENT      (token with repo contents + issues write + repo ref create)
      JIRA_ISSUE_KEY
      ISSUE_NUMBER
  - Python package: requests
"""
import os
import sys
import base64
import mimetypes
import json
import requests
from pathlib import Path

def env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and not v:
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return v

GITHUB_REPOSITORY = env("GITHUB_REPOSITORY", required=True)
GH_TOKEN = env("GH_PAT_AGENT", required=True)
JIRA_ISSUE_KEY = env("JIRA_ISSUE_KEY", required=True)
ISSUE_NUMBER = env("ISSUE_NUMBER", required=True)
ATTACHMENTS_DIR = env("ATTACHMENTS_DIR", "attachments")
ATTACHMENTS_BRANCH = env("ATTACHMENTS_BRANCH", "attachments")

API_BASE = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}"

HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "upload-attachments-script"
}

def list_local_files(dirpath):
    p = Path(dirpath)
    if not p.exists() or not p.is_dir():
        return []
    return [x for x in sorted(p.iterdir()) if x.is_file()]

def get_default_branch():
    r = requests.get(API_BASE, headers=HEADERS)
    r.raise_for_status()
    return r.json().get("default_branch")

def branch_exists(branch):
    r = requests.get(f"{API_BASE}/branches/{branch}", headers=HEADERS)
    return r.status_code == 200

def create_branch_from_default(branch, default_branch):
    # Get default branch ref sha
    r = requests.get(f"{API_BASE}/git/refs/heads/{default_branch}", headers=HEADERS)
    r.raise_for_status()
    sha = r.json()["object"]["sha"]
    payload = {"ref": f"refs/heads/{branch}", "sha": sha}
    r = requests.post(f"{API_BASE}/git/refs", headers=HEADERS, json=payload)
    if r.status_code not in (201, 200):
        print("Failed to create branch:", r.status_code, r.text)
        r.raise_for_status()
    return True

def get_file_sha(path, branch):
    r = requests.get(f"{API_BASE}/contents/{path}", headers=HEADERS, params={"ref": branch})
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def upload_file(path, content_b64, message, branch, sha=None):
    payload = {"message": message, "content": content_b64, "branch": branch}
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{API_BASE}/contents/{path}", headers=HEADERS, json=payload)
    if r.status_code not in (201, 200):
        # raise with helpful info
        raise RuntimeError(f"Upload failed for {path}: {r.status_code} {r.text}")
    return r.json()

def post_issue_comment(issue_number, body):
    r = requests.post(f"{API_BASE}/issues/{issue_number}/comments", headers=HEADERS, json={"body": body})
    r.raise_for_status()
    return r.json()

def sanitize_filename(name: str) -> str:
    # replace spaces, remove characters except alnum, dot, underscore, hyphen
    s = name.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch in "._-")
    return s or "file"

def main():
    files = list_local_files(ATTACHMENTS_DIR)
    if not files:
        print(f"No files in {ATTACHMENTS_DIR}; nothing to do.")
        return

    default_branch = get_default_branch()
    print("default_branch:", default_branch)

    if not branch_exists(ATTACHMENTS_BRANCH):
        print(f"Branch {ATTACHMENTS_BRANCH} does not exist; creating from {default_branch}")
        create_branch_from_default(ATTACHMENTS_BRANCH, default_branch)
    else:
        print(f"Branch {ATTACHMENTS_BRANCH} exists")

    uploaded_urls = []

    for fpath in files:
        fname = sanitize_filename(fpath.name)
        repo_path = f"attachments/{JIRA_ISSUE_KEY}/{fname}"
        message = f"Add Jira attachment {fname} for {JIRA_ISSUE_KEY}"
        # read file and base64 encode
        with open(fpath, "rb") as fh:
            data = fh.read()
        b64 = base64.b64encode(data).decode("ascii")

        existing_sha = get_file_sha(repo_path, ATTACHMENTS_BRANCH)
        try:
            print(f"Uploading {fpath} -> {repo_path} (existing_sha={existing_sha})")
            upload_file(repo_path, b64, message, ATTACHMENTS_BRANCH, sha=existing_sha)
        except Exception as e:
            print("Upload failed for", repo_path, ":", e, file=sys.stderr)
            continue

        raw_url = f"{RAW_BASE}/{ATTACHMENTS_BRANCH}/{repo_path}"
        uploaded_urls.append((fname, raw_url))

    if not uploaded_urls:
        print("No files uploaded successfully; skipping comment.")
        return

    # Build comment body
    body_lines = [f"Uploaded Jira attachments for {JIRA_ISSUE_KEY}:\n"]
    for fname, url in uploaded_urls:
        body_lines.append(f"![{fname}]({url})\n")
    body = "\n".join(body_lines)

    # Post comment
    try:
        resp = post_issue_comment(ISSUE_NUMBER, body)
        print("Comment posted:", resp.get("html_url"))
    except Exception as e:
        print("Failed to post comment:", e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
