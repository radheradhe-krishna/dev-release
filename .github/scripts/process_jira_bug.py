
"""
Zero-Cost Jira Bug Processor
Runs entirely on GitHub Actions - No external servers needed!
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from github import Github
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import time

# Add parent directory to path to import from issue_creator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the issue body generator
from issue_generator import IssueBodyGenerator
# Import the correct github client that doesn't strip assignees
from issue_creator.github_client import create_issue_with_gh

# Configuration from GitHub Secrets
CONFIG = {
    'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
    'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
    'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
    'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN'),
    'GITHUB_REPOSITORY': os.environ.get('GITHUB_REPOSITORY')
}


class JiraGitHubProcessor:
    """Main processor class"""
    
    def __init__(self, bug_key):
        self.bug_key = bug_key
        self.bug_data = None
        self.attachments = []
        self.github_issue_number = None
        self.github_issue_url = None
        
    def run(self):
        """Main execution flow"""
        print("=" * 70)
        print("🐍 Python Zero-Cost Jira Bug Processor")
        print("=" * 70)
        print(f"Processing bug: {self.bug_key}")
        print()
        
        try:
            # Step 1: Fetch bug details from Jira
            self.fetch_bug_from_jira()
            
            # Step 2: Download and store attachments
            self.process_attachments()
            
            # Step 3: Upload attachments to GitHub Release
            if self.attachments:
                self.upload_to_github_release()
            
            # Step 4: Create GitHub issue
            # self.create_github_issue()
            self.create_github_issue11()

            # Step 5: Assign Copilot to the issue
            # self.assign_copilot_to_issue()

            # Step 6: Update Jira with GitHub link
            self.update_jira()
            
            print()
            print("=" * 70)
            print("✅ Processing Complete!")
            print("=" * 70)
            print(f"Jira Bug:      {self.bug_key}")
            print(f"GitHub Issue:  #{self.github_issue_number}")
            print(f"Attachments:   {len(self.attachments)}")
            print()
            
            return 0
            
        except Exception as e:
            print(f"❌ Error: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    
    def fetch_bug_from_jira(self):
        """Fetch complete bug details from Jira"""
        print("📥 Fetching bug details from Jira...")
        
        url = f"{CONFIG['JIRA_BASE_URL']}/rest/api/3/issue/{self.bug_key}"
        
        # Create Basic Auth header
        auth_string = f"{CONFIG['JIRA_EMAIL']}:{CONFIG['JIRA_API_TOKEN']}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8'))
        auth_header = f"Basic {auth_bytes.decode('utf-8')}"
        
        request = urllib.request.Request(url)
        request.add_header('Authorization', auth_header)
        request.add_header('Accept', 'application/json')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.bug_data = json.loads(response.read().decode('utf-8'))
                print(f"✅ Fetched bug: {self.bug_data['key']}")
                print(f"   Summary: {self.bug_data['fields']['summary']}")
                
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP Error: {e.code} - {e.reason}")
            error_body = e.read().decode('utf-8')
            print(f"   Response: {error_body}")
            raise
    
    def process_attachments(self):
        """Download attachments and store locally"""
        attachments_data = self.bug_data['fields'].get('attachment', [])
        
        if not attachments_data:
            print("📎 No attachments found")
            return
        
        print(f"📎 Processing {len(attachments_data)} attachment(s)...")
        
        # Create directory for attachments
        attachments_dir = Path('attachments')
        attachments_dir.mkdir(exist_ok=True)
        
        for attachment in attachments_data:
            try:
                filename = attachment['filename']
                file_url = attachment['content']
                file_size = attachment['size']
                
                print(f"   Downloading: {filename} ({self._format_size(file_size)})")
                
                # Download file
                file_data = self._download_from_jira(file_url)
                
                # Save to disk
                file_path = attachments_dir / filename
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                self.attachments.append({
                    'filename': filename,
                    'path': str(file_path),
                    'size': file_size,
                    'mime_type': attachment.get('mimeType', 'application/octet-stream'),
                    'github_url': None  # Will be set after upload
                })
                
                print(f"   ✅ Downloaded: {filename}")
                
            except Exception as e:
                print(f"   ⚠️  Failed to download {filename}: {str(e)}")
                continue
        
        print(f"✅ Downloaded {len(self.attachments)} attachment(s)")
    
    def _download_from_jira(self, url):
        """Download file from Jira"""
        auth_string = f"{CONFIG['JIRA_EMAIL']}:{CONFIG['JIRA_API_TOKEN']}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8'))
        auth_header = f"Basic {auth_bytes.decode('utf-8')}"
        
        request = urllib.request.Request(url)
        request.add_header('Authorization', auth_header)
        
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    
    def upload_to_github_release(self):
        """Upload attachments to GitHub Release"""
        print(f"📦 Creating GitHub Release for attachments...")
        
        owner, repo = CONFIG['GITHUB_REPOSITORY'].split('/')
        
        # Create release
        release_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        release_tag = f"jira-{self.bug_key.lower()}-{int(time.time())}"
        
        release_data = {
            'tag_name': release_tag,
            'name': f"Attachments: {self.bug_key}",
            'body': f"Attachments for Jira bug [{self.bug_key}]({CONFIG['JIRA_BASE_URL']}/browse/{self.bug_key})",
            'draft': False,
            'prerelease': True
        }
        
        request = urllib.request.Request(
            release_url,
            data=json.dumps(release_data).encode('utf-8'),
            method='POST'
        )
        request.add_header('Authorization', f"Bearer {CONFIG['GITHUB_TOKEN']}")
        request.add_header('Accept', 'application/vnd.github+json')
        request.add_header('Content-Type', 'application/json')
        request.add_header('X-GitHub-Api-Version', '2022-11-28')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.loads(response.read().decode('utf-8'))
                upload_url = release['upload_url'].replace('{?name,label}', '')
                
                print(f"✅ Release created: {release_tag}")
                print(f"   Upload URL: {upload_url}")
                
                # Upload each attachment
                for attachment in self.attachments:
                    self._upload_asset(upload_url, attachment)
                    
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
                error_data = json.loads(error_body)
                error_msg = error_data.get('message', error_body)
            except Exception:
                error_msg = e.reason
            
            print(f"⚠️  Failed to create release: {e.code} - {error_msg}")
            print(f"   Attachments will be listed in issue without download links")
        except Exception as e:
            print(f"⚠️  Unexpected error creating release: {str(e)}")            
            print(f"   Attachments will be listed in issue without download links")
    

    def _upload_asset(self, upload_url, attachment):
        """Upload single file as release asset"""
        print(f"   Uploading: {attachment['filename']} ({self._format_size(attachment['size'])})")

        try:
            with open(attachment['path'], 'rb') as f:
                file_data = f.read()
        except Exception as e:
            print(f"   ⚠️  Failed to read file {attachment['filename']}: {str(e)}")
            return
            
        # URL-encode the filename (spaces/special chars)
        safe_name = quote(attachment['filename'], safe='')
        asset_url = f"{upload_url}?name={safe_name}"

        request = urllib.request.Request(asset_url, data=file_data, method='POST')
        request.add_header('Authorization', f"Bearer {CONFIG['GITHUB_TOKEN']}")
        request.add_header('Accept', 'application/vnd.github+json')
        request.add_header('Content-Type', attachment.get('mime_type', 'application/octet-stream'))
        request.add_header('Content-Length', str(len(file_data)))
        request.add_header('X-GitHub-Api-Version', '2022-11-28')

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                asset = json.loads(response.read().decode('utf-8'))
                attachment['github_url'] = asset.get('browser_download_url')
                print(f"   ✅ Uploaded: {attachment['filename']}")
                print(f"      URL: {attachment['github_url']}")
        except urllib.error.HTTPError as e:
            # Print the response body to help troubleshooting
            try:
                body = e.read().decode('utf-8')
                error_data = json.loads(body)
                error_msg = error_data.get('message', body)
            except Exception:
                body = '<no body>'
            error_msg = e.reason
            
            print(f"   ⚠️  Failed to upload {attachment['filename']}: {e.code} - {error_msg}")
            if e.code == 403:
                print(f"      Hint: Check that workflow has 'contents: write' permission")
            elif e.code == 422:
                print(f"      Hint: Asset might already exist or filename is invalid")
        except Exception as e:
            print(f"   ⚠️  Unexpected error uploading {attachment['filename']}: {str(e)}")

    def create_github_issue11(self):
        load_dotenv()
        jira_issue_key = 'Bug'
        jira_summary = 'Summary'
        
        """Create GitHub issue with bug details and attachment links11"""
        print("🔨 Creating GitHub issue11...")
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
        
        gh, repo = self.ensure_repo(token, repo_name)
        
        # Don't pass assignees during creation - will be assigned via GitHub Actions workflow step
        # This avoids the "user not found" error that prevents issue creation
        assignees = []
        print("Note: Assignees will be set via GitHub Actions workflow after issue creation")
    
        labels = ["jira-auto-fix"]
        # Create the issue (pass repo to get an Issue object when possible)

        title = f"{jira_summary} - {jira_issue_key}"
        # Use the issue generator to create the body
        generator = IssueBodyGenerator()
        body = generator.generate(self.bug_data, CONFIG, self.attachments)
        created = create_issue_with_gh(
            title=title,
            body=body,
            assignees=assignees,
            labels=labels,
            gh_token=token,
            repo_obj=repo,
        )
        
        # Store the created issue information
        if created and hasattr(created, 'number'):
            self.github_issue_number = created.number
            self.github_issue_url = created.html_url
            print(f"✅ Issue created: #{self.github_issue_number}")
            print(f"   Copilot assignment will be handled by GitHub Actions workflow")
        elif isinstance(created, str):
            # Got URL string from CLI
            self.github_issue_url = created
            # Extract issue number from URL
            import re
            match = re.search(r'/issues/(\d+)', created)
            if match:
                self.github_issue_number = int(match.group(1))
            print(f"✅ Issue created: {self.github_issue_url}")
            print(f"   Copilot assignment will be handled by GitHub Actions workflow")
          
    
    def ensure_repo(self, token: str, repo_name: str):
        try:
            gh = Github(token)
            repo = gh.get_repo(repo_name)
            print(f"Connected to repository: {repo.full_name}")
            return gh, repo
        except Exception as exc:
            print(f"Error connecting to GitHub: {exc}")
            sys.exit(1)

    def create_github_issue(self):
        """Create GitHub issue with bug details and attachment links"""
        print("🔨 Creating GitHub issue...")
        
        fields = self.bug_data['fields']
        
        # Use the issue generator to create the body
        generator = IssueBodyGenerator()
        issue_body = generator.generate(self.bug_data, CONFIG, self.attachments)
        
        # Extract fields for labels
        bug_type = fields.get('issuetype', {}).get('name', 'Bug')
        priority = fields.get('priority', {}).get('name', 'Medium')
        components = [c['name'] for c in fields.get('components', [])]
        labels = fields.get('labels', [])
        
        # Prepare API request
        owner, repo = CONFIG['GITHUB_REPOSITORY'].split('/')
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        
        issue_labels = ['jira-bug', 'automated']
        
        # Add priority label
        priority_lower = priority.lower()
        issue_labels.append(priority_lower)
        
        # Add component labels
        if components:
            issue_labels.extend([f"component:{comp.lower().replace(' ', '-')}" for comp in components])
        
        # Add Jira labels
        issue_labels.extend(labels)
        
        # Add bug type if it's not "Bug"
        if bug_type.lower() != 'bug':
            issue_labels.append(f"type:{bug_type.lower().replace(' ', '-')}")
            
        issue_data = {
            'title': f"[{self.bug_key}] {fields['summary']}",
            'body': issue_body,
            'labels': issue_labels,
            # 'assignees': ['copilot-swe-agent']  # Assign to GitHub Copilot hrutvipujar-sudo
        }
        
        request = urllib.request.Request(
            url,
            data=json.dumps(issue_data).encode('utf-8'),
            method='POST'
        )
        request.add_header('Authorization', f"Bearer {CONFIG['GITHUB_TOKEN']}")
        request.add_header('Accept', 'application/vnd.github+json')
        request.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.github_issue_number = result['number']
                self.github_issue_url = result['html_url']
                print(f"✅ Created GitHub issue #{self.github_issue_number}")
                print(f"   URL: {self.github_issue_url}")
                
        except urllib.error.HTTPError as e:
            print(f"❌ Failed to create GitHub issue: {e.code} - {e.reason}")
            print(f"   Response: {e.read().decode('utf-8')}")
            raise
    
    def assign_copilot_to_issue(self):
        """Assign GitHub Copilot to the created issue"""
        print("🤖 Assigning Copilot to the issue...")
        
        owner, repo = CONFIG['GITHUB_REPOSITORY'].split('/')
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{self.github_issue_number}/assignees"
        
        # Assign with optional agent assignment parameters
        assignee_data = {
            'assignees': ['copilot-swe-agent[bot]']
        }
        
        request = urllib.request.Request(
            url,
            data=json.dumps(assignee_data).encode('utf-8'),
            method='POST'
        )
        request.add_header('Authorization', f"Bearer {CONFIG['GITHUB_TOKEN']}")
        request.add_header('Accept', 'application/vnd.github+json')
        request.add_header('Content-Type', 'application/json')
        request.add_header('X-GitHub-Api-Version', '2022-11-28')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                print(f"✅ Assigned Copilot to issue #{self.github_issue_number}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"⚠️  Failed to assign Copilot: {e.code} - {e.reason}")
            print(f"   Response: {error_body}")
            # Don't raise - this is optional
    
    def update_jira(self):
        """Add comment to Jira with GitHub issue link"""
        print("🔗 Updating Jira with GitHub link...")
        
        url = f"{CONFIG['JIRA_BASE_URL']}/rest/api/3/issue/{self.bug_key}/comment"
        
        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "🔗 GitHub Issue created: "
                            },
                            {
                                "type": "text",
                                "text": f"#{self.github_issue_number}",
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {
                                            "href": self.github_issue_url
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        
        auth_string = f"{CONFIG['JIRA_EMAIL']}:{CONFIG['JIRA_API_TOKEN']}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8'))
        auth_header = f"Basic {auth_bytes.decode('utf-8')}"
        
        request = urllib.request.Request(
            url,
            data=json.dumps(comment_data).encode('utf-8'),
            method='POST'
        )
        request.add_header('Authorization', auth_header)
        request.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                print(f"✅ Updated Jira with GitHub link")
                
        except urllib.error.HTTPError as e:
            print(f"⚠️  Failed to update Jira: {e.code} - {e.reason}")
    
    @staticmethod
    def _format_size(size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        bug_key = sys.argv[1]
    else:
        bug_key = os.environ.get('JIRA_BUG_KEY')
    
    if not bug_key:
        print("❌ Error: Bug key not provided", file=sys.stderr)
        return 1
    
    missing = [k for k, v in CONFIG.items() if not v]
    if missing:
        print(f"❌ Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 1
    
    processor = JiraGitHubProcessor(bug_key)
    return processor.run()

if __name__ == '__main__':
    sys.exit(main())


