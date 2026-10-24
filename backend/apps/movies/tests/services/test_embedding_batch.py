from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from apps.movies.exceptions import EmbeddingUnavailableError
from apps.movies.models import EmbeddingBatchJob, Genre, Movie
from apps.movies.services import embedding_batch as embedding_batch_module
from apps.movies.services.embedding_batch import (
    SUBMIT_LOCK_KEY,
    _apply_results,
    _finish_failed,
    collect_finished_batches,
    movie_to_metadata,
    pending_movies_queryset,
    submit_pending_embeddings_batch,
)
from apps.movies.services.embedding_text import build_embedding_text


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)



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

    def test_excludes_an_embedded_movie_that_has_no_target_hash(self, movie):
        movie.embedding = EMBEDDING_VECTOR
        movie.embedding_target_hash = ""
        movie.embedding_source_hash = "legacy"
        movie.embedding_batch = None
        movie.save()

        assert list(pending_movies_queryset()) == []

    def test_includes_a_movie_without_embedding_even_if_the_hashes_match(self, movie):
        movie.embedding = None
        movie.embedding_target_hash = "same-hash"
        movie.embedding_source_hash = "same-hash"
        movie.embedding_batch = None
        movie.save()

        assert list(pending_movies_queryset()) == [movie]

    def test_lists_every_pending_movie(self, movie):
        other = Movie.objects.create(tmdb_id=12346, title="Second", release_year=2022)

        assert set(pending_movies_queryset()) == {movie, other}


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

    def test_directors_default_to_an_empty_list(self, movie):
        movie.directors = None
        movie.save()

        assert movie_to_metadata(movie)["directors"] == []

    def test_lists_every_genre_by_name(self, movie):
        movie.genres.add(
            Genre.objects.create(name="Drama"), Genre.objects.create(name="Comedy")
        )

        names = {g["name"] for g in movie_to_metadata(movie)["genres"]}

        assert names == {"Drama", "Comedy"}

    def test_language_and_runtime_are_passed_through(self, movie):
        movie.original_language = "fr"
        movie.runtime = None
        movie.save()

        result = movie_to_metadata(movie)

        assert result["original_language"] == "fr"
        assert result["runtime"] is None


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

    def _pending(self, tmdb_id, title):
        return Movie.objects.create(tmdb_id=tmdb_id, title=title, release_year=2000)

    def test_min_items_above_the_pending_count_skips_the_submission(self):
        self._pending(1001, "One")
        self._pending(1002, "Two")
        client = MagicMock()

        result = submit_pending_embeddings_batch(client=client, min_items=3)

        assert result is None
        client.create_batch.assert_not_called()
        assert not EmbeddingBatchJob.objects.exists()

    def test_only_the_prefix_that_fits_the_remaining_budget_is_submitted(self):
        movies = [self._pending(1001 + i, f"Film {i}") for i in range(3)]
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        with patch("apps.movies.services.embedding_batch.api_quota.remaining", return_value=25), patch(
            "apps.movies.services.embedding_batch.api_quota.text_cost", return_value=10
        ):
            job = submit_pending_embeddings_batch(client=client)

        ordered = sorted(movies, key=lambda m: str(m.pk))
        expected = ordered[:2]

        assert [item[0] for item in job.items] == [
            str(m.pk) for m in expected
        ]
        assert client.create_batch.call_args.kwargs["cost"] == 20
        assert len(client.create_batch.call_args.args[0]) == 2

        for m in movies:
            m.refresh_from_db()

        selected_ids = {m.pk for m in expected}

        assert {
            m.pk for m in movies if m.embedding_batch_id == job.pk
        } == selected_ids

        assert {
            m.pk for m in movies if m.embedding_batch_id is None
        } == {m.pk for m in movies} - selected_ids

    def test_an_unlimited_budget_submits_every_pending_movie(self):
        movies = [self._pending(1001 + i, f"Film {i}") for i in range(3)]
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        with patch("apps.movies.services.embedding_batch.api_quota.remaining", return_value=None), patch(
            "apps.movies.services.embedding_batch.api_quota.text_cost", return_value=10
        ):
            job = submit_pending_embeddings_batch(client=client)

        assert len(job.items) == 3
        assert client.create_batch.call_args.kwargs["cost"] == 30
        assert {m.pk for m in Movie.objects.filter(embedding_batch=job)} == {m.pk for m in movies}

    def test_the_cost_of_each_text_is_computed_for_the_batch_quota(self):
        self._pending(1001, "One")
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        with patch("apps.movies.services.embedding_batch.api_quota.text_cost", return_value=10) as text_cost:
            submit_pending_embeddings_batch(client=client)

        assert text_cost.call_args.args[0] == "embedding_batch"

    def test_movies_whose_text_is_blank_are_not_submitted(self):
        blank = self._pending(1001, "Blank")
        filled = self._pending(1002, "Filled")
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        def fake_build_embedding_text(metadata):
            if metadata["title"] == "Blank":
                return "  "
            return "usable text"

        with patch(
            "apps.movies.services.embedding_batch.build_embedding_text",
            side_effect=fake_build_embedding_text,
        ):
            job = submit_pending_embeddings_batch(client=client)

        assert [item[0] for item in job.items] == [str(filled.pk)]

        blank.refresh_from_db()
        filled.refresh_from_db()

        assert blank.embedding_batch_id is None
        assert filled.embedding_batch_id == job.pk

    def test_nothing_is_submitted_when_every_text_is_blank(self):
        self._pending(1001, "Blank")
        client = MagicMock()

        with patch("apps.movies.services.embedding_batch.build_embedding_text", return_value=""):
            result = submit_pending_embeddings_batch(client=client)

        assert result is None
        client.create_batch.assert_not_called()
        assert not EmbeddingBatchJob.objects.exists()

    def test_the_default_maximum_is_used_when_none_is_given(self, monkeypatch):
        self._pending(1001, "One")
        self._pending(1002, "Two")
        monkeypatch.setattr(embedding_batch_module, "DEFAULT_MAX_ITEMS", 1)
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        job = submit_pending_embeddings_batch(client=client)

        assert len(job.items) == 1

    def test_movies_are_submitted_in_primary_key_order(self):
        movies = [self._pending(1003, "C"), self._pending(1001, "A"), self._pending(1002, "B")]
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        job = submit_pending_embeddings_batch(client=client)

        ordered = sorted(movies, key=lambda m: m.pk)
        assert [item[0] for item in job.items] == [str(m.pk) for m in ordered]
        assert client.create_batch.call_args.args[0] == [
            build_embedding_text(movie_to_metadata(m)) for m in ordered
        ]

    def test_movies_that_already_belong_to_a_batch_are_not_submitted_again(self):
        busy = self._pending(1001, "Busy")
        free = self._pending(1002, "Free")
        other_job = EmbeddingBatchJob.objects.create(job_name="other", items=[])
        Movie.objects.filter(pk=busy.pk).update(embedding_batch=other_job)
        client = MagicMock()
        client.create_batch.return_value = "batch-1"

        job = submit_pending_embeddings_batch(client=client)

        assert [item[0] for item in job.items] == [str(free.pk)]

    def test_a_client_failure_creates_no_job_and_leaves_the_movies_free(self):
        movie = self._pending(1001, "One")
        client = MagicMock()
        client.create_batch.side_effect = EmbeddingUnavailableError("down")

        with pytest.raises(EmbeddingUnavailableError):
            submit_pending_embeddings_batch(client=client)

        movie.refresh_from_db()
        assert movie.embedding_batch_id is None
        assert not EmbeddingBatchJob.objects.exists()

    def test_a_default_client_is_created_when_none_is_given(self):
        self._pending(1001, "One")

        with patch("apps.movies.services.embedding_batch.EmbeddingClient") as client_cls:
            client_cls.return_value.create_batch.return_value = "batch-from-default"
            job = submit_pending_embeddings_batch()

        client_cls.assert_called_once_with()
        assert job.job_name == "batch-from-default"

    def test_the_lock_is_released_when_there_is_nothing_to_submit(self):
        submit_pending_embeddings_batch(client=MagicMock())

        assert cache.get(SUBMIT_LOCK_KEY) is None

    def test_a_lock_held_by_another_submission_is_left_alone(self):
        cache.add(SUBMIT_LOCK_KEY, "1", timeout=600)

        submit_pending_embeddings_batch(client=MagicMock())

        assert cache.get(SUBMIT_LOCK_KEY) == "1"


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

    def _job(self, name, movie, *, state=None, cost=10):
        job = EmbeddingBatchJob.objects.create(
            job_name=name, items=[[str(movie.pk), "hash-" + name, cost]]
        )
        if state is not None:
            job.state = state
            job.save(update_fields=["state"])
        Movie.objects.filter(pk=movie.pk).update(embedding_batch=job)
        return job

    def test_jobs_that_are_no_longer_submitted_are_not_polled(self):
        EmbeddingBatchJob.objects.create(
            job_name="done", items=[], state=EmbeddingBatchJob.State.SUCCEEDED
        )
        EmbeddingBatchJob.objects.create(
            job_name="broken", items=[], state=EmbeddingBatchJob.State.FAILED
        )
        client = MagicMock()

        result = collect_finished_batches(client=client)

        client.get_batch.assert_not_called()
        assert result["pending"] == 0

    def test_the_summary_adds_up_every_job(self, movie):
        second = Movie.objects.create(tmdb_id=12346, title="Second", release_year=2022)
        third = Movie.objects.create(tmdb_id=12347, title="Third", release_year=2023)
        self._job("ok", movie)
        self._job("waiting", second)
        self._job("broken", third)
        results = {
            "ok": SimpleNamespace(
                done=True, succeeded=True, state="JOB_STATE_SUCCEEDED", error=None,
                embeddings=[EMBEDDING_VECTOR], item_errors=[None],
            ),
            "waiting": SimpleNamespace(
                done=False, succeeded=False, state="JOB_STATE_RUNNING", error=None,
                embeddings=None, item_errors=None,
            ),
            "broken": SimpleNamespace(
                done=True, succeeded=False, state="JOB_STATE_FAILED", error="boom",
                embeddings=None, item_errors=None,
            ),
        }
        client = MagicMock()
        client.get_batch.side_effect = lambda name: results[name]

        with patch("apps.movies.services.embedding_batch.api_quota.refund"):
            summary = collect_finished_batches(client=client)

        assert summary == {
            "succeeded": 1, "failed": 1, "pending": 1, "embedded": 1, "item_errors": 0,
        }

    def test_a_successful_job_is_stamped_with_its_finish_time(self, movie):
        job = self._job("ok", movie)
        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True, succeeded=True, state="JOB_STATE_SUCCEEDED", error=None,
            embeddings=[EMBEDDING_VECTOR], item_errors=[None],
        )

        collect_finished_batches(client=client)

        job.refresh_from_db()
        assert job.finished_at is not None

    def test_item_errors_without_a_message_get_a_default_one(self, movie, caplog):
        self._job("partial", movie, cost=9)
        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True, succeeded=True, state="JOB_STATE_PARTIALLY_SUCCEEDED", error=None,
            embeddings=[None], item_errors=[],
        )

        with patch("apps.movies.services.embedding_batch.api_quota.refund") as refund, caplog.at_level("ERROR"):
            summary = collect_finished_batches(client=client)

        assert summary["item_errors"] == 1
        assert summary["embedded"] == 0
        refund.assert_called_once_with("embedding_batch", 9)
        assert "Unknown embedding error." in caplog.text

    def test_a_successful_batch_without_embeddings_is_a_count_mismatch(self, movie):
        job = self._job("empty", movie, cost=15)
        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True, succeeded=True, state="JOB_STATE_SUCCEEDED", error=None,
            embeddings=None, item_errors=None,
        )

        with patch("apps.movies.services.embedding_batch.api_quota.refund") as refund:
            summary = collect_finished_batches(client=client)

        job.refresh_from_db()
        assert summary["failed"] == 1
        assert job.state == EmbeddingBatchJob.State.FAILED
        assert job.error == "Result count mismatch: expected 1, got 0."
        refund.assert_called_once_with("embedding_batch", 15)

    @pytest.mark.parametrize(
        ("state", "error", "expected"),
        [
            ("JOB_STATE_FAILED", "boom", "JOB_STATE_FAILED: boom"),
            ("JOB_STATE_CANCELLED", None, "JOB_STATE_CANCELLED: "),
            ("JOB_STATE_EXPIRED", "too slow", "JOB_STATE_EXPIRED: too slow"),
        ],
    )
    def test_a_failed_job_records_the_state_and_the_error(self, movie, state, error, expected):
        job = self._job("broken", movie)
        client = MagicMock()
        client.get_batch.return_value = SimpleNamespace(
            done=True, succeeded=False, state=state, error=error, embeddings=None
        )

        with patch("apps.movies.services.embedding_batch.api_quota.refund"):
            collect_finished_batches(client=client)

        job.refresh_from_db()
        assert job.error == expected

    def test_no_client_is_created_when_there_is_nothing_to_poll(self):
        with patch("apps.movies.services.embedding_batch.EmbeddingClient") as client_cls:
            collect_finished_batches()

        client_cls.assert_not_called()

    def test_a_default_client_is_created_when_there_are_jobs(self, movie):
        self._job("waiting", movie)

        with patch("apps.movies.services.embedding_batch.EmbeddingClient") as client_cls:
            client_cls.return_value.get_batch.return_value = SimpleNamespace(
                done=False, succeeded=False, state="JOB_STATE_RUNNING", error=None,
                embeddings=None,
            )
            summary = collect_finished_batches()

        client_cls.assert_called_once_with()
        client_cls.return_value.get_batch.assert_called_once_with("waiting")
        assert summary["pending"] == 1


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

    def _job(self, movie, text_hash="hash-1", cost=10):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-1", items=[[str(movie.pk), text_hash, cost]]
        )
        Movie.objects.filter(pk=movie.pk).update(embedding_batch=job)
        return job

    def test_a_movie_without_target_hash_gets_the_embedding_and_both_hashes(self, movie):
        job = self._job(movie)
        Movie.objects.filter(pk=movie.pk).update(embedding_target_hash="")

        embedded, errors = _apply_results(job, [EMBEDDING_VECTOR], [])

        movie.refresh_from_db()
        assert (embedded, errors) == (1, 0)
        assert movie.embedding == EMBEDDING_VECTOR
        assert movie.embedding_source_hash == "hash-1"
        assert movie.embedding_target_hash == "hash-1"

    def test_movies_outside_the_job_are_not_touched(self, movie):
        bystander = Movie.objects.create(tmdb_id=12346, title="Bystander", release_year=2022)
        job = self._job(movie)

        _apply_results(job, [EMBEDDING_VECTOR], [])

        bystander.refresh_from_db()
        assert bystander.embedding is None
        assert bystander.embedding_source_hash == ""

    def test_a_movie_that_no_longer_exists_is_not_counted(self, movie):
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-1", items=[["00000000-0000-0000-0000-000000000001", "hash-1", 10]]
        )

        embedded, errors = _apply_results(job, [EMBEDDING_VECTOR], [])

        assert (embedded, errors) == (0, 0)
        job.refresh_from_db()
        assert job.state == EmbeddingBatchJob.State.SUCCEEDED

    def test_the_failed_cost_of_every_item_is_refunded_in_one_call(self, movie):
        other = Movie.objects.create(tmdb_id=12346, title="Second", release_year=2022)
        third = Movie.objects.create(tmdb_id=12347, title="Third", release_year=2023)
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-1",
            items=[
                [str(movie.pk), "h1", 7],
                [str(other.pk), "h2", 8],
                [str(third.pk), "h3", 5],
            ],
        )

        with patch("apps.movies.services.embedding_batch.api_quota.refund") as refund:
            embedded, errors = _apply_results(
                job, [None, EMBEDDING_VECTOR, None], ["bad", None, "worse"]
            )

        assert (embedded, errors) == (1, 2)
        refund.assert_called_once_with("embedding_batch", 12)

    def test_nothing_is_refunded_when_every_item_succeeds(self, movie):
        job = self._job(movie)

        with patch("apps.movies.services.embedding_batch.api_quota.refund") as refund:
            _apply_results(job, [EMBEDDING_VECTOR], [])

        refund.assert_not_called()

    def test_item_errors_are_logged_by_position(self, movie, caplog):
        other = Movie.objects.create(tmdb_id=12346, title="Second", release_year=2022)
        job = EmbeddingBatchJob.objects.create(
            job_name="batch-1",
            items=[[str(movie.pk), "h1", 1], [str(other.pk), "h2", 1]],
        )

        with patch("apps.movies.services.embedding_batch.api_quota.refund"), caplog.at_level("ERROR"):
            _apply_results(job, [None, None], ["first failed"])

        assert "first failed" in caplog.text
        assert "Unknown embedding error." in caplog.text

    def test_the_job_is_marked_as_succeeded_and_stamped(self, movie):
        job = self._job(movie)

        _apply_results(job, [EMBEDDING_VECTOR], [])

        job.refresh_from_db()
        assert job.state == EmbeddingBatchJob.State.SUCCEEDED
        assert job.finished_at is not None


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

    def test_the_error_message_is_truncated_to_2000_characters(self, movie):
        job = EmbeddingBatchJob.objects.create(job_name="batch-1", items=[])

        with patch("apps.movies.services.embedding_batch.api_quota.refund"):
            _finish_failed(job, "x" * 3000)

        job.refresh_from_db()
        assert len(job.error) == 2000

    def test_only_the_movies_of_that_job_are_released(self, movie):
        other = Movie.objects.create(tmdb_id=12346, title="Second", release_year=2022)
        failing = EmbeddingBatchJob.objects.create(
            job_name="failing", items=[[str(movie.pk), "h1", 10]]
        )
        healthy = EmbeddingBatchJob.objects.create(
            job_name="healthy", items=[[str(other.pk), "h2", 10]]
        )
        Movie.objects.filter(pk=movie.pk).update(embedding_batch=failing)
        Movie.objects.filter(pk=other.pk).update(embedding_batch=healthy)

        with patch("apps.movies.services.embedding_batch.api_quota.refund"):
            _finish_failed(failing, "boom")

        other.refresh_from_db()
        healthy.refresh_from_db()
        assert other.embedding_batch_id == healthy.pk
        assert healthy.state == EmbeddingBatchJob.State.SUBMITTED
