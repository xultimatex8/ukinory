from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from apps.movies.models import EmbeddingBatchJob, Genre, Movie
from apps.movies.services.embedding_batch import (
    SUBMIT_LOCK_KEY,
    _apply_results,
    _finish_failed,
    collect_finished_batches,
    movie_to_metadata,
    pending_movies_queryset,
    submit_pending_embeddings_batch,
)


EMBEDDING_VECTOR = [0.1] * 768


@pytest.mark.django_db
class TestPendingMoviesQueryset:
    def test_includes_movie_without_embedding(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        assert list(pending_movies_queryset()) == [movie]

    def test_includes_movie_with_changed_target_hash(self, movie):
        movie.embedding = EMBEDDING_VECTOR
        movie.embedding_target_hash = "new-hash"
        movie.embedding_source_hash = "old-hash"
        movie.embedding_batch = None
        movie.save()

        assert list(pending_movies_queryset()) == [movie]

    def test_excludes_movie_with_current_embedding(self, movie):
        movie.embedding = EMBEDDING_VECTOR
        movie.embedding_target_hash = "same-hash"
        movie.embedding_source_hash = "same-hash"
        movie.embedding_batch = None
        movie.save()

        assert list(pending_movies_queryset()) == []

    def test_excludes_movie_already_in_batch(self, movie):
        job = EmbeddingBatchJob.objects.create(
            job_name="existing-job",
            items=[],
        )

        movie.embedding = None
        movie.embedding_batch = job
        movie.save()

        assert list(pending_movies_queryset()) == []


@pytest.mark.django_db
class TestMovieToMetadata:
    def test_builds_expected_metadata(self, movie):
        genre = Genre.objects.create(name="Science Fiction")

        movie.title = "Dune"
        movie.release_year = 2021
        movie.wikidata_description = "A science fiction film."
        movie.directors = ["Denis Villeneuve"]
        movie.original_language = "en"
        movie.runtime = 155
        movie.save()

        movie.genres.add(genre)

        result = movie_to_metadata(movie)

        assert result == {
            "title": "Dune",
            "release_year": 2021,
            "wikidata_description": "A science fiction film.",
            "genres": [{"name": "Science Fiction"}],
            "directors": ["Denis Villeneuve"],
            "original_language": "en",
            "runtime": 155,
        }

    def test_uses_empty_description_when_missing(self, movie):
        movie.wikidata_description = None
        movie.genres.all = MagicMock(return_value=[])

        result = movie_to_metadata(movie)

        assert result["wikidata_description"] == ""
        assert result["genres"] == []


@pytest.mark.django_db
class TestSubmitPendingEmbeddingsBatch:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        cache.clear()

    def test_returns_none_when_budget_is_exhausted(self, movie):
        with patch(
            "apps.movies.services.embedding_batch.api_quota.remaining",
            return_value=0,
        ), patch(
            "apps.movies.services.embedding_batch.EmbeddingClient"
        ) as mock_client:
            result = submit_pending_embeddings_batch()

        assert result is None
        mock_client.assert_not_called()

    def test_returns_none_when_submission_lock_is_already_taken(self, movie):
        cache.add(SUBMIT_LOCK_KEY, "1", timeout=600)

        with patch(
            "apps.movies.services.embedding_batch.EmbeddingClient"
        ) as mock_client:
            result = submit_pending_embeddings_batch()

        assert result is None
        mock_client.assert_not_called()

    def test_returns_none_when_not_enough_pending_movies(self):
        result = submit_pending_embeddings_batch(min_items=1)

        assert result is None
        assert not EmbeddingBatchJob.objects.exists()

    def test_submits_pending_movies_and_creates_job(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        client = MagicMock()
        client.create_batch.return_value = "batch-123"

        with (
            patch(
                "apps.movies.services.embedding_batch.build_embedding_text",
                return_value="movie embedding text",
            ),
            patch(
                "apps.movies.services.embedding_batch.embedding_hash",
                return_value="text-hash",
            ),
            patch(
                "apps.movies.services.embedding_batch.api_quota.text_cost",
                return_value=10,
            ),
        ):
            job = submit_pending_embeddings_batch(
                client=client,
                min_items=1,
            )

        assert job is not None
        assert job.job_name == "batch-123"
        assert job.items == [[str(movie.pk), "text-hash", 10]]

        movie.refresh_from_db()
        assert movie.embedding_batch_id == job.pk

        client.create_batch.assert_called_once()

        args, kwargs = client.create_batch.call_args

        assert args[0] == ["movie embedding text"]
        assert kwargs["display_name"].startswith("catalog-embeddings-")
        assert kwargs["cost"] == 10

    def test_does_not_create_empty_batch_when_budget_cannot_fit_movie(
        self,
        movie,
    ):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        with (
            patch(
                "apps.movies.services.embedding_batch.api_quota.remaining",
                return_value=5,
            ),
            patch(
                "apps.movies.services.embedding_batch.build_embedding_text",
                return_value="movie embedding text",
            ),
            patch(
                "apps.movies.services.embedding_batch.embedding_hash",
                return_value="text-hash",
            ),
            patch(
                "apps.movies.services.embedding_batch.api_quota.text_cost",
                return_value=10,
            ),
        ):
            client = MagicMock()

            result = submit_pending_embeddings_batch(
                client=client,
                min_items=1,
            )

        assert result is None
        client.create_batch.assert_not_called()
        assert not EmbeddingBatchJob.objects.exists()

    def test_limits_submission_to_max_items(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        second = Movie.objects.create(
            tmdb_id=12346,
            title="Second movie",
            release_year=2022,
        )

        client = MagicMock()
        client.create_batch.return_value = "batch-123"

        with (
            patch(
                "apps.movies.services.embedding_batch.build_embedding_text",
                side_effect=["text-1", "text-2"],
            ),
            patch(
                "apps.movies.services.embedding_batch.embedding_hash",
                side_effect=["hash-1", "hash-2"],
            ),
            patch(
                "apps.movies.services.embedding_batch.api_quota.text_cost",
                return_value=10,
            ),
        ):
            job = submit_pending_embeddings_batch(
                client=client,
                max_items=1,
                min_items=1,
            )

        assert job is not None
        assert len(job.items) == 1

        expected_movie = min(
            (movie, second),
            key=lambda item: str(item.pk),
        )

        assert job.items[0][0] == str(expected_movie.pk)

        movie.refresh_from_db()
        second.refresh_from_db()

        selected = movie if movie.pk == expected_movie.pk else second
        not_selected = second if movie.pk == expected_movie.pk else movie

        assert selected.embedding_batch_id == job.pk
        assert not_selected.embedding_batch_id is None


    def test_releases_submission_lock_after_success(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        client = MagicMock()
        client.create_batch.return_value = "batch-123"

        with (
            patch(
                "apps.movies.services.embedding_batch.build_embedding_text",
                return_value="text",
            ),
            patch(
                "apps.movies.services.embedding_batch.embedding_hash",
                return_value="hash",
            ),
            patch(
                "apps.movies.services.embedding_batch.api_quota.text_cost",
                return_value=10,
            ),
        ):
            submit_pending_embeddings_batch(client=client)

        assert cache.get(SUBMIT_LOCK_KEY) is None

    def test_releases_submission_lock_when_client_fails(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = ""
        movie.embedding_batch = None
        movie.save()

        client = MagicMock()
        client.create_batch.side_effect = RuntimeError("boom")

        with (
            patch(
                "apps.movies.services.embedding_batch.build_embedding_text",
                return_value="text",
            ),
            patch(
                "apps.movies.services.embedding_batch.embedding_hash",
                return_value="hash",
            ),
            patch(
                "apps.movies.services.embedding_batch.api_quota.text_cost",
                return_value=10,
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            submit_pending_embeddings_batch(client=client)

        assert cache.get(SUBMIT_LOCK_KEY) is None


@pytest.mark.django_db
class TestCollectFinishedBatches:
    def make_job(self, movie, *, state=None, items=None):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-123",
            items=items
            or [[str(movie.pk), "hash-1", 10]],
        )

        if state is not None:
            job.state = state
            job.save(update_fields=["state"])

        movie.embedding_batch = job
        movie.save(update_fields=["embedding_batch"])

        return job

    def test_returns_empty_summary_when_there_are_no_jobs(self):
        client = MagicMock()

        result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 0,
            "failed": 0,
            "pending": 0,
            "embedded": 0,
            "item_errors": 0,
        }

        client.get_batch.assert_not_called()

    def test_keeps_job_pending_when_batch_is_not_done(self, movie):
        job = self.make_job(movie)

        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=False,
            succeeded=False,
            state="JOB_STATE_RUNNING",
            error=None,
            embeddings=None,
        )

        result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 0,
            "failed": 0,
            "pending": 1,
            "embedded": 0,
            "item_errors": 0,
        }

        job.refresh_from_db()
        assert job.state == EmbeddingBatchJob.State.SUBMITTED

    def test_marks_failed_batch_as_failed(self, movie):
        job = self.make_job(movie)

        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True,
            succeeded=False,
            state="JOB_STATE_FAILED",
            error="Something went wrong",
            embeddings=None,
        )

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 0,
            "failed": 1,
            "pending": 0,
            "embedded": 0,
            "item_errors": 0,
        }

        job.refresh_from_db()
        movie.refresh_from_db()

        assert job.state == EmbeddingBatchJob.State.FAILED
        assert job.error == "JOB_STATE_FAILED: Something went wrong"
        assert movie.embedding_batch_id is None

        refund.assert_called_once()

    def test_marks_failed_when_result_count_does_not_match(self, movie):
        job = self.make_job(movie)

        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True,
            succeeded=True,
            state="JOB_STATE_SUCCEEDED",
            error=None,
            embeddings=[],
        )

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            result = collect_finished_batches(client=client)

        assert result["failed"] == 1
        assert result["succeeded"] == 0

        job.refresh_from_db()
        movie.refresh_from_db()

        assert job.state == EmbeddingBatchJob.State.FAILED
        assert "Result count mismatch" in job.error
        assert movie.embedding_batch_id is None

        refund.assert_called_once()

    def test_applies_successful_embeddings(self, movie):
        job = self.make_job(movie)

        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True,
            succeeded=True,
            state="JOB_STATE_SUCCEEDED",
            error=None,
            embeddings=[EMBEDDING_VECTOR],
            item_errors=[],
        )

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 1,
            "failed": 0,
            "pending": 0,
            "embedded": 1,
            "item_errors": 0,
        }

        movie.refresh_from_db()
        job.refresh_from_db()

        assert movie.embedding == EMBEDDING_VECTOR
        assert movie.embedding_source_hash == "hash-1"
        assert movie.embedding_target_hash == "hash-1"
        assert movie.embedding_batch_id is None
        assert job.state == EmbeddingBatchJob.State.SUCCEEDED

        refund.assert_not_called()

    def test_counts_item_errors_and_refunds_failed_item_cost(self, movie):
        second = Movie.objects.create(
            tmdb_id=12346,
            title="Second movie",
            release_year=2022,
        )

        job = EmbeddingBatchJob.objects.create(
            job_name="batch-123",
            items=[
                [str(movie.pk), "hash-1", 10],
                [str(second.pk), "hash-2", 20],
            ],
        )

        movie.embedding_batch = job
        second.embedding_batch = job

        Movie.objects.bulk_update(
            [movie, second],
            ["embedding_batch"],
        )

        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True,
            succeeded=True,
            state="JOB_STATE_SUCCEEDED",
            error=None,
            embeddings=[EMBEDDING_VECTOR, None],
            item_errors=[None, "Embedding failed"],
        )

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 1,
            "failed": 0,
            "pending": 0,
            "embedded": 1,
            "item_errors": 1,
        }

        movie.refresh_from_db()
        second.refresh_from_db()

        assert movie.embedding == EMBEDDING_VECTOR
        assert second.embedding is None
        assert movie.embedding_batch_id is None
        assert second.embedding_batch_id is None

        refund.assert_called_once_with("embedding_batch", 20)

    def test_keeps_batch_pending_when_polling_is_unavailable(self, movie):
        from apps.movies.exceptions import EmbeddingUnavailableError

        self.make_job(movie)

        client = MagicMock()
        client.get_batch.side_effect = EmbeddingUnavailableError("temporary failure")

        result = collect_finished_batches(client=client)

        assert result == {
            "succeeded": 0,
            "failed": 0,
            "pending": 1,
            "embedded": 0,
            "item_errors": 0,
        }


@pytest.mark.django_db
class TestApplyResults:
    def test_does_not_overwrite_changed_target_hash(self, movie):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-123",
            items=[[str(movie.pk), "old-hash", 10]],
        )

        movie.embedding_batch = job
        movie.embedding_target_hash = "new-hash"
        movie.embedding_source_hash = "old-hash"
        movie.save()

        embedded, errors = _apply_results(
            job,
            [EMBEDDING_VECTOR],
            [],
        )

        movie.refresh_from_db()
        job.refresh_from_db()

        assert embedded == 0
        assert errors == 0
        assert movie.embedding is None
        assert movie.embedding_batch_id is None
        assert job.state == EmbeddingBatchJob.State.SUCCEEDED

    def test_refunds_cost_for_none_vector(self, movie):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-123",
            items=[[str(movie.pk), "hash-1", 25]],
        )

        movie.embedding_batch = job
        movie.save(update_fields=["embedding_batch"])

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            embedded, errors = _apply_results(
                job,
                [None],
                ["Embedding failed"],
            )

        assert embedded == 0
        assert errors == 1

        refund.assert_called_once_with("embedding_batch", 25)

        movie.refresh_from_db()
        job.refresh_from_db()

        assert movie.embedding_batch_id is None
        assert job.state == EmbeddingBatchJob.State.SUCCEEDED


@pytest.mark.django_db
class TestFinishFailed:
    def test_marks_job_failed_clears_movies_and_refunds_cost(self, movie):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-123",
            items=[
                [str(movie.pk), "hash-1", 10],
                ["other-movie", "hash-2", 20],
            ],
        )

        movie.embedding_batch = job
        movie.save(update_fields=["embedding_batch"])

        with patch(
            "apps.movies.services.embedding_batch.api_quota.refund"
        ) as refund:
            _finish_failed(job, "batch failed")

        job.refresh_from_db()
        movie.refresh_from_db()

        assert job.state == EmbeddingBatchJob.State.FAILED
        assert job.error == "batch failed"
        assert job.finished_at is not None
        assert movie.embedding_batch_id is None

        refund.assert_called_once_with("embedding_batch", 30)
