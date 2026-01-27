#!/usr/bin/env python3
"""
Test for optional JIRA_SUMMARY handling in main.py.
"""
import os
import sys
from unittest import mock
import pytest

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_create_issue_from_jira_without_summary():
    """Test that create_issue_from_jira works when JIRA_SUMMARY is not provided."""
    with mock.patch.dict(os.environ, {
        'JIRA_ISSUE_KEY': 'TEST-123',
        'JIRA_SUMMARY': '',
        'JIRA_DESCRIPTION': 'Test description',
        'GH_PAT_AGENT': 'test-token',
        'GITHUB_REPOSITORY': 'test/repo',
        'DRY_RUN': 'true'  # Use dry-run to avoid actual API calls
    }, clear=False):
        # Import after setting env vars
        from main import create_issue_from_jira
        
        # Should not raise an error even without summary
        # In dry-run mode, it should just print and return
        try:
            create_issue_from_jira()
            # If we get here without exception, the test passes
            assert True
        except SystemExit as e:
            # If it exits with code 1, that means it failed validation
            if e.code == 1:
                pytest.fail("create_issue_from_jira should not exit when JIRA_SUMMARY is empty")


def test_create_issue_from_jira_with_summary():
    """Test that create_issue_from_jira works when JIRA_SUMMARY is provided."""
    with mock.patch.dict(os.environ, {
        'JIRA_ISSUE_KEY': 'TEST-456',
        'JIRA_SUMMARY': 'Test Summary',
        'JIRA_DESCRIPTION': 'Test description',
        'GH_PAT_AGENT': 'test-token',
        'GITHUB_REPOSITORY': 'test/repo',
        'DRY_RUN': 'true'  # Use dry-run to avoid actual API calls
    }, clear=False):
        # Import after setting env vars
        from main import create_issue_from_jira
        
        # Should work fine with summary
        try:
            create_issue_from_jira()
            assert True
        except SystemExit as e:
            if e.code == 1:
                pytest.fail("create_issue_from_jira should work with JIRA_SUMMARY provided")


def test_create_issue_from_jira_without_issue_key():
    """Test that create_issue_from_jira fails when JIRA_ISSUE_KEY is not provided."""
    with mock.patch.dict(os.environ, {
        'JIRA_ISSUE_KEY': '',
        'JIRA_SUMMARY': 'Test Summary',
        'JIRA_DESCRIPTION': 'Test description',
        'GH_PAT_AGENT': 'test-token',
        'GITHUB_REPOSITORY': 'test/repo',
    }, clear=False):
        # Import after setting env vars
        from main import create_issue_from_jira
        
        # Should exit with error code 1 when issue key is missing
        with pytest.raises(SystemExit) as exc_info:
            create_issue_from_jira()
        assert exc_info.value.code == 1
