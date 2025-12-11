## Jira Bug Report
- **Issue Key:** {jira_issue_key}
- **Summary:** {jira_summary}

## Description / Reproduction steps
{jira_description}

## Attachments / Images
If there are attachments (screenshots, logs, or other files) provided with this issue, inspect them carefully:
- Open screenshots and logs for timestamps, stack traces, configuration snippets, or UI clues.
- If images contain text, run OCR or zoom in to extract any visible text or error messages.
- Note filenames and any metadata that could help narrow the affected components.
- Include any useful findings from attachments in your analysis and PR description.

## Goal
Analyze the issue, attempt to reproduce it using the steps above, and make minimal, correct code changes to fix the bug.

## Required behavior
- Reproduce the bug locally (or document why reproduction is not possible).
- Produce a focused fix that modifies existing files only (no new top-level services).
- Add tests that verify the bug is fixed and prevent regressions.
- Add comments in changed files only when they are necessary to explain non-obvious decisions.

## Acceptance criteria
- The bug is reproducible or a clear analysis explains why it cannot be reproduced.
- Code changes are minimal and limited to the components involved.
- Unit/integration tests validate the fix and pass in CI.
- PR references this Jira key and contains clear validation steps, including any relevant findings from attachments.

## Suggested steps for implementation
1. Search the repository for relevant files, tests, and configurations related to the reported behavior.
2. Try to reproduce the bug using the steps in "Description / Reproduction steps". Record exact commands/inputs you used.
3. Inspect any attachments (screenshots/logs). Extract error messages, stack traces, config snippets, or UI details and include them in the PR/issue comment.
4. If you cannot reproduce, add an issue comment explaining what was tried and why reproduction failed; do not create new files.
5. If reproducible, add a minimal fix in existing files, and add/adjust tests to cover the scenario.
6. Run the full test suite, fix any failures caused by the change, and keep changes focused.
7. Add comments only where necessary to clarify non-obvious logic; avoid excessive comments.
8. Create a branch named: `fix/{jira_issue_key}-brief-description` (e.g. `fix/SCRUM-35-add-india-currency`) and open a PR referencing this Jira key.
9. In the PR description include: files changed, tests added, how to validate locally (commands/inputs), and any follow-up tasks.

---

## Instructions for Copilot Coding Agent
Follow these steps precisely:
1. Inspect the repo for files likely related to this issue; list the files you examined in the PR description.
2. Download and inspect attachments (images, logs) included with the Jira issue. For images: view at full resolution and run OCR if they contain text. Record any useful findings (filenames, timestamps[...]
3. Attempt to reproduce the issue using the reproduction steps provided in the issue body. Record the exact steps and results.
4. If you cannot reproduce, stop and add a detailed comment explaining attempts and reasoning.
5. If you can reproduce, implement a minimal fix modifying only existing files.
6. Add tests that reproduce the bug and verify the fix. Keep tests small and deterministic.
7. Run unit tests and CI checks; include test results in the PR description.
8. Keep inline comments minimal—only when necessary to clarify intent or non-obvious code.
9. Do NOT modify .gitignore.
10. Create a branch as described above, open a PR referencing the Jira key, and in the PR description include:
   - Files changed
   - Tests added
   - How to validate locally (commands and sample inputs)
   - Any remaining risks or follow-up tasks

When finished, post a final comment on the issue summarizing:
- Whether the bug was reproducible
- Files changed, tests added, and findings from attachments
- How to validate the fix locally
- Any open follow-ups or limitations
