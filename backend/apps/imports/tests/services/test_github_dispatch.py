from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.imports.services.github_dispatch import trigger_import_worker

URL = (
    "https://api.github.com/repos/owner/repo/actions/workflows/"
    "process-imports.yml/dispatches"
)


@pytest.fixture
def configured(settings):
    settings.DEBUG = False
    settings.GITHUB_DISPATCH_TOKEN = "secret-token"
    settings.GITHUB_REPO = "owner/repo"
    settings.GITHUB_WORKFLOW_FILE = "process-imports.yml"
    settings.GITHUB_DISPATCH_REF = "main"
    return settings


@pytest.fixture
def mock_post():
    with patch("requests.post") as post:
        post.return_value = MagicMock(ok=True, status_code=204, text="")
        yield post


class TestSkipped:
    def test_skips_dispatch_in_debug_mode(self, configured, mock_post, caplog):
        configured.DEBUG = True

        with caplog.at_level(logging.DEBUG):
            trigger_import_worker()

        mock_post.assert_not_called()
        assert "DEBUG is True" in caplog.text

    @pytest.mark.parametrize("token", [None, ""])
    def test_skips_dispatch_without_token(
        self, configured, mock_post, caplog, token
    ):
        configured.GITHUB_DISPATCH_TOKEN = token

        with caplog.at_level(logging.INFO):
            trigger_import_worker()

        mock_post.assert_not_called()
        assert "not configured" in caplog.text

    @pytest.mark.parametrize("repo", [None, ""])
    def test_skips_dispatch_without_repo(
        self, configured, mock_post, caplog, repo
    ):
        configured.GITHUB_REPO = repo

        with caplog.at_level(logging.INFO):
            trigger_import_worker()

        mock_post.assert_not_called()
        assert "not configured" in caplog.text


class TestDispatch:
    def test_posts_workflow_dispatch_with_expected_request(
        self, configured, mock_post
    ):
        trigger_import_worker()

        mock_post.assert_called_once_with(
            URL,
            headers={
                "Authorization": "Bearer secret-token",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"ref": "main"},
            timeout=5,
        )

    def test_uses_custom_workflow_file_and_ref(self, configured, mock_post):
        configured.GITHUB_WORKFLOW_FILE = "custom.yml"
        configured.GITHUB_DISPATCH_REF = "production"

        trigger_import_worker()

        args, kwargs = mock_post.call_args
        assert args[0] == (
            "https://api.github.com/repos/owner/repo/actions/workflows/"
            "custom.yml/dispatches"
        )
        assert kwargs["json"] == {"ref": "production"}

    def test_successful_dispatch_logs_no_warning(
        self, configured, mock_post, caplog
    ):
        with caplog.at_level(logging.WARNING):
            trigger_import_worker()

        assert caplog.records == []

    def test_returns_none(self, configured, mock_post):
        assert trigger_import_worker() is None


class TestFailures:
    def test_error_response_is_logged_and_does_not_raise(
        self, configured, mock_post, caplog
    ):
        mock_post.return_value = MagicMock(
            ok=False, status_code=422, text="unprocessable"
        )

        with caplog.at_level(logging.WARNING):
            trigger_import_worker()

        assert "dispatch failed (422)" in caplog.text
        assert "unprocessable" in caplog.text

    def test_error_response_body_is_truncated_to_300_characters(
        self, configured, mock_post, caplog
    ):
        mock_post.return_value = MagicMock(
            ok=False, status_code=500, text="x" * 500
        )

        with caplog.at_level(logging.WARNING):
            trigger_import_worker()

        assert "x" * 300 in caplog.text
        assert "x" * 301 not in caplog.text

    @pytest.mark.parametrize(
        "error",
        [
            requests.ConnectionError("no route"),
            requests.Timeout("too slow"),
            requests.RequestException("generic"),
        ],
    )
    def test_request_exceptions_are_logged_and_swallowed(
        self, configured, mock_post, caplog, error
    ):
        mock_post.side_effect = error

        with caplog.at_level(logging.WARNING):
            trigger_import_worker()

        assert "dispatch request failed" in caplog.text
        assert caplog.records[-1].exc_info is not None

    def test_non_request_exceptions_are_not_swallowed(
        self, configured, mock_post
    ):
        mock_post.side_effect = ValueError("bug")

        with pytest.raises(ValueError):
            trigger_import_worker()
