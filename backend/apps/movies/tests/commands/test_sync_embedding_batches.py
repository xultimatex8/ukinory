from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.movies.exceptions import EmbeddingError


class TestSeedEmbeddingBatchCommand:
    TARGET_COLLECT = (
        "apps.movies.management.commands.sync_embedding_batches."
        "collect_finished_batches"
    )
    TARGET_SUBMIT = (
        "apps.movies.management.commands.sync_embedding_batches."
        "submit_pending_embeddings_batch"
    )
    TARGET_ENVIRONMENT = (
        "apps.movies.management.commands.sync_embedding_batches."
        "settings.ENVIRONMENT"
    )

    def test_collects_and_submits_successfully(self):
        job = SimpleNamespace(
            job_name="batch-123",
            items=[["1", "hash", 10]],
        )

        with (
            patch(
                self.TARGET_COLLECT,
                return_value={
                    "succeeded": 1,
                    "failed": 0,
                    "pending": 0,
                    "embedded": 1,
                    "item_errors": 0,
                },
            ) as mock_collect,
            patch(
                self.TARGET_SUBMIT,
                return_value=job,
            ) as mock_submit,
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            out = StringIO()
            call_command("sync_embedding_batches", stdout=out)

        mock_collect.assert_called_once_with()
        mock_submit.assert_called_once_with(
            max_items=None,
            min_items=1,
        )

        output = out.getvalue()
        assert "Collect:" in output
        assert "Submit: batch-123 (1 movies)." in output

    def test_collect_only_does_not_submit(self):
        with (
            patch(
                self.TARGET_COLLECT,
                return_value={
                    "succeeded": 1,
                    "failed": 0,
                    "pending": 0,
                    "embedded": 1,
                    "item_errors": 0,
                },
            ) as mock_collect,
            patch(self.TARGET_SUBMIT) as mock_submit,
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            out = StringIO()
            call_command(
                "sync_embedding_batches",
                "--collect-only",
                stdout=out,
            )

        mock_collect.assert_called_once_with()
        mock_submit.assert_not_called()

        assert "Collect:" in out.getvalue()

    def test_submit_only_does_not_collect(self):
        job = SimpleNamespace(
            job_name="batch-123",
            items=[["1", "hash", 10]],
        )

        with (
            patch(self.TARGET_COLLECT) as mock_collect,
            patch(
                self.TARGET_SUBMIT,
                return_value=job,
            ) as mock_submit,
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            out = StringIO()
            call_command(
                "sync_embedding_batches",
                "--submit-only",
                stdout=out,
            )

        mock_collect.assert_not_called()
        mock_submit.assert_called_once_with(
            max_items=None,
            min_items=1,
        )

        assert "Submit: batch-123 (1 movies)." in out.getvalue()

    def test_passes_max_items_and_min_items(self):
        with (
            patch(
                self.TARGET_COLLECT,
                return_value={
                    "succeeded": 0,
                    "failed": 0,
                    "pending": 0,
                    "embedded": 0,
                    "item_errors": 0,
                },
            ),
            patch(
                self.TARGET_SUBMIT,
                return_value=None,
            ) as mock_submit,
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            out = StringIO()
            call_command(
                "sync_embedding_batches",
                "--max-items",
                "100",
                "--min-items",
                "5",
                stdout=out,
            )

        mock_submit.assert_called_once_with(
            max_items=100,
            min_items=5,
        )
        assert "Submit: nothing submitted." in out.getvalue()

    def test_does_not_submit_when_no_job_is_returned(self):
        with (
            patch(
                self.TARGET_COLLECT,
                return_value={
                    "succeeded": 0,
                    "failed": 0,
                    "pending": 0,
                    "embedded": 0,
                    "item_errors": 0,
                },
            ),
            patch(
                self.TARGET_SUBMIT,
                return_value=None,
            ),
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            out = StringIO()
            call_command("sync_embedding_batches", stdout=out)

        assert "Submit: nothing submitted." in out.getvalue()

    def test_reports_and_propagates_embedding_error(self):
        with (
            patch(
                self.TARGET_COLLECT,
                side_effect=EmbeddingError("boom"),
            ),
            patch(self.TARGET_ENVIRONMENT, "production"),
        ):
            err = StringIO()

            with pytest.raises(EmbeddingError):
                call_command("sync_embedding_batches", stderr=err)

        assert "Embedding batch sync failed: boom" in err.getvalue()

    def test_skips_when_environment_is_not_production(self):
        with (
            patch(self.TARGET_COLLECT) as mock_collect,
            patch(self.TARGET_SUBMIT) as mock_submit,
            patch(self.TARGET_ENVIRONMENT, "development"),
        ):
            out = StringIO()
            call_command("sync_embedding_batches", stdout=out)

        mock_collect.assert_not_called()
        mock_submit.assert_not_called()

        assert (
            "Embedding batch sync skipped: environment is not production."
            in out.getvalue()
        )
