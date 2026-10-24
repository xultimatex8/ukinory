from __future__ import annotations

import math
import time
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError

from apps.common import api_quota
from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError
from apps.movies.services.embedding_client import (
    BATCH_DONE_STATES,
    BATCH_RESULT_STATES,
    DEFAULT_SYNC_CHUNK_SIZE,
    DIMENSIONS,
    EMBEDDING_PACING_KEY,
    QUOTA_BATCH,
    QUOTA_SYNC,
    EmbeddingClient,
    _fit_dimensions,
)


class FakeAPIError(APIError):
    def __init__(self, code: int):
        self.code = code
        Exception.__init__(self, f"fake api error {code}")


@pytest.fixture(autouse=True)
def embedding_api_key(settings):
    settings.GEMINI_API_KEY = "test-key"


@pytest.fixture(autouse=True)
def mock_genai_client_class(monkeypatch):
    mock_client_cls = MagicMock()
    monkeypatch.setattr(
        "apps.movies.services.embedding_client.genai.Client", mock_client_cls
    )
    return mock_client_cls


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def mock_wait_for_pacing(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(
        "apps.movies.services.embedding_client.wait_for_pacing", mock
    )
    return mock


def make_client(**overrides) -> EmbeddingClient:
    return EmbeddingClient(**overrides)


def embed_response(values: list[float]):
    embedding = MagicMock()
    embedding.values = values

    response = MagicMock()
    response.embeddings = [embedding]

    return response


class TestConfiguration:
    def test_missing_api_key_raises(self, settings):
        settings.GEMINI_API_KEY = None

        with pytest.raises(EmbeddingError, match="GEMINI_API_KEY is not configured"):
            EmbeddingClient(api_key=None)

    def test_explicit_api_key_overrides_settings(self, settings):
        settings.GEMINI_API_KEY = "from-settings"

        client = EmbeddingClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"

    def test_uses_default_model(self):
        client = EmbeddingClient()

        assert client.model == "gemini-embedding-001"

    def test_uses_default_min_request_interval(self):
        client = EmbeddingClient()

        assert client.min_request_interval == 0.85


class TestEmbedHappyPath:
    def test_returns_normalized_embedding_values(self):
        client = make_client()
        values = [0.1] * DIMENSIONS

        client._client.models.embed_content.return_value = embed_response(values)

        result = client.embed("some movie text")

        expected_value = 1 / math.sqrt(DIMENSIONS)
        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )

    def test_sends_configured_model_text(self):
        client = make_client(model="custom-model")
        client._client.models.embed_content.return_value = embed_response(
            [0.0] * DIMENSIONS
        )

        client.embed("some movie text")

        _, kwargs = client._client.models.embed_content.call_args

        assert kwargs["model"] == "custom-model"
        assert kwargs["contents"] == ["some movie text"]
        assert kwargs["config"] == {"output_dimensionality": DIMENSIONS}


class TestEmbedValidation:
    def test_dimension_mismatch_raises_embedding_error(self):
        client = make_client()

        client._client.models.embed_content.return_value = embed_response(
            [0.1, 0.2, 0.3]
        )

        with pytest.raises(EmbeddingError):
            client.embed("some movie text")


class TestRateLimiting:
    def test_429_retries_and_then_succeeds(self):
        client = make_client(max_retries=2)
        values = [1.0] * DIMENSIONS

        client._client.models.embed_content.side_effect = [
            FakeAPIError(429),
            embed_response(values),
        ]

        result = client.embed("text")

        expected_value = 1 / math.sqrt(DIMENSIONS)

        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )
        assert client._client.models.embed_content.call_count == 2

    def test_429_exhausted_raises_unavailable(self):
        client = make_client(max_retries=1)
        client._client.models.embed_content.side_effect = FakeAPIError(429)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        assert client._client.models.embed_content.call_count == 2


class TestServerErrors:
    def test_5xx_retries_and_then_succeeds(self):
        client = make_client(max_retries=2)
        values = [1.0] * DIMENSIONS

        client._client.models.embed_content.side_effect = [
            FakeAPIError(500),
            embed_response(values),
        ]

        result = client.embed("text")

        expected_value = 1 / math.sqrt(DIMENSIONS)

        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )
        assert client._client.models.embed_content.call_count == 2

    def test_5xx_exhausted_raises_unavailable(self):
        client = make_client(max_retries=1)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        assert client._client.models.embed_content.call_count == 2


class TestPacing:
    """Pacing itself (locking, backoff, sleeping) is redis_pacing's job and is
    covered by its own tests. Here we only verify EmbeddingClient delegates
    to it with the right key and interval, on every attempt."""

    def test_calls_wait_for_pacing_with_configured_key_and_interval(
        self, mock_wait_for_pacing
    ):
        client = make_client(min_request_interval=0.5)
        client._client.models.embed_content.return_value = embed_response(
            [0.0] * DIMENSIONS
        )

        client.embed("text")

        mock_wait_for_pacing.assert_called_once_with(EMBEDDING_PACING_KEY, 0.5)

    def test_paces_before_every_attempt_including_retries(
        self, mock_wait_for_pacing
    ):
        client = make_client(max_retries=1)
        values = [1.0] * DIMENSIONS

        client._client.models.embed_content.side_effect = [
            FakeAPIError(429),
            embed_response(values),
        ]

        client.embed("text")

        assert mock_wait_for_pacing.call_count == 2
        mock_wait_for_pacing.assert_called_with(
            EMBEDDING_PACING_KEY, client.min_request_interval
        )

    def test_paces_even_when_request_ultimately_raises(
        self, mock_wait_for_pacing
    ):
        client = make_client(max_retries=0)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        mock_wait_for_pacing.assert_called_once_with(
            EMBEDDING_PACING_KEY, client.min_request_interval
        )


def one_hot(index: int) -> list[float]:
    return [1.0 if i == index else 0.0 for i in range(DIMENSIONS)]


def echo_embed(**kwargs):
    """Fake embed_content: the text 'tN' is embedded as the N-th unit vector."""
    embeddings = []
    for text in kwargs["contents"]:
        embedding = MagicMock()
        embedding.values = one_hot(int(text[1:]))
        embeddings.append(embedding)
    response = MagicMock()
    response.embeddings = embeddings
    return response


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(time, "sleep", recorded.append)
    return recorded


class TestFitDimensions:
    def test_exact_length_vectors_are_normalised(self):
        values = [3.0, 4.0] + [0.0] * (DIMENSIONS - 2)

        result = _fit_dimensions(values)

        assert result[:2] == pytest.approx([0.6, 0.8])
        assert math.sqrt(sum(v * v for v in result)) == pytest.approx(1.0)

    def test_longer_vectors_are_truncated_before_normalising(self):
        result = _fit_dimensions([1.0] * (DIMENSIONS + 10))

        assert len(result) == DIMENSIONS
        assert result == pytest.approx([1 / math.sqrt(DIMENSIONS)] * DIMENSIONS)

    def test_a_zero_vector_is_returned_unchanged(self):
        assert _fit_dimensions([0.0] * DIMENSIONS) == [0.0] * DIMENSIONS

    def test_shorter_vectors_are_rejected(self):
        with pytest.raises(
            EmbeddingError, match=f"Expected {DIMENSIONS} embedding dimensions, got 3"
        ):
            _fit_dimensions([0.1, 0.2, 0.3])

    def test_the_input_list_is_not_modified(self):
        values = [2.0] * (DIMENSIONS + 1)

        _fit_dimensions(values)

        assert values == [2.0] * (DIMENSIONS + 1)


class TestClientCreation:
    def test_the_genai_client_is_built_with_the_api_key(self, mock_genai_client_class):
        client = EmbeddingClient(api_key="explicit-key")

        mock_genai_client_class.assert_called_once_with(api_key="explicit-key")
        assert client._client is mock_genai_client_class.return_value

    def test_the_api_key_falls_back_to_settings(self, mock_genai_client_class):
        EmbeddingClient()

        mock_genai_client_class.assert_called_once_with(api_key="test-key")

    def test_no_request_has_been_made_yet(self):
        assert make_client()._last_request_at is None


class TestEmbedMany:
    def test_empty_input_makes_no_request(self, mock_wait_for_pacing):
        client = make_client()

        assert client.embed_many([]) == []

        client._client.models.embed_content.assert_not_called()
        mock_wait_for_pacing.assert_not_called()

    def test_texts_are_sent_in_chunks_and_order_is_preserved(self):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        result = client.embed_many([f"t{i}" for i in range(5)], chunk_size=2)

        calls = client._client.models.embed_content.call_args_list
        assert [c.kwargs["contents"] for c in calls] == [["t0", "t1"], ["t2", "t3"], ["t4"]]
        assert [v.index(1.0) for v in result] == [0, 1, 2, 3, 4]

    def test_default_chunk_size_is_used(self):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        client.embed_many([f"t{i}" for i in range(DEFAULT_SYNC_CHUNK_SIZE * 2 + 1)])

        assert client._client.models.embed_content.call_count == 3

    def test_every_chunk_is_paced(self, mock_wait_for_pacing):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        client.embed_many(["t0", "t1", "t2"], chunk_size=1)

        assert mock_wait_for_pacing.call_count == 3

    def test_a_wrong_number_of_embeddings_is_an_error_and_is_not_retried(self):
        client = make_client(max_retries=3)
        client._client.models.embed_content.return_value = embed_response([0.1] * DIMENSIONS)

        with pytest.raises(EmbeddingError, match="Expected 2 embeddings, got 1"):
            client.embed_many(["t0", "t1"])

        assert client._client.models.embed_content.call_count == 1

    def test_embed_returns_the_first_vector(self):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        assert client.embed("t7").index(1.0) == 7


class TestRetryBehaviour:
    def test_backoff_grows_exponentially_between_attempts(self, sleeps):
        client = make_client(max_retries=3)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("t0")

        assert sleeps == [0.5, 1.0, 2.0]
        assert client._client.models.embed_content.call_count == 4

    @pytest.mark.parametrize(
        ("attempt", "expected"),
        [(1, 0.5), (2, 1.0), (3, 2.0), (4, 4.0), (5, 8.0), (6, 16.0), (7, 16.0), (20, 16.0)],
    )
    def test_backoff_is_capped(self, sleeps, attempt, expected):
        EmbeddingClient._sleep_backoff(attempt)

        assert sleeps == [expected]

    def test_exhausted_rate_limit_is_reported_as_rate_limited(self):
        client = make_client(max_retries=1)
        client._client.models.embed_content.side_effect = FakeAPIError(429)

        with pytest.raises(EmbeddingUnavailableError, match="rate-limited after 2 attempt") as info:
            client.embed("t0")

        assert isinstance(info.value.__cause__, APIError)

    def test_other_exhausted_errors_are_reported_as_failed(self):
        client = make_client(max_retries=0)
        client._client.models.embed_content.side_effect = FakeAPIError(503)

        with pytest.raises(EmbeddingUnavailableError, match="failed after 1 attempt"):
            client.embed("t0")

    def test_errors_that_are_not_api_errors_are_not_retried(self, sleeps):
        client = make_client(max_retries=3)
        client._client.models.embed_content.side_effect = RuntimeError("bug")

        with pytest.raises(RuntimeError, match="bug"):
            client.embed("t0")

        assert client._client.models.embed_content.call_count == 1
        assert sleeps == []

    def test_the_time_of_the_last_request_is_recorded(self):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        client.embed("t0")

        assert client._last_request_at is not None


class TestSyncQuota:
    def test_quota_is_consumed_for_the_cost_of_every_text(self):
        client = make_client()
        client._client.models.embed_content.side_effect = echo_embed

        with patch.object(api_quota, "text_cost", return_value=4), patch.object(
            api_quota, "consume"
        ) as consume:
            client.embed_many(["t0", "t1", "t2"], chunk_size=2)

        assert [c.args for c in consume.call_args_list] == [(QUOTA_SYNC, 8), (QUOTA_SYNC, 4)]

    def test_quota_is_consumed_again_on_every_retry(self):
        client = make_client(max_retries=2)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with patch.object(api_quota, "text_cost", return_value=3), patch.object(
            api_quota, "consume"
        ) as consume:
            with pytest.raises(EmbeddingUnavailableError):
                client.embed("t0")

        assert consume.call_count == 3
        assert all(c.args == (QUOTA_SYNC, 3) for c in consume.call_args_list)

    def test_an_exhausted_quota_is_reported_as_unavailable_without_calling_the_api(self):
        client = make_client()

        with patch.object(
            api_quota, "consume", side_effect=api_quota.QuotaExceeded(QUOTA_SYNC, "day", 100)
        ):
            with pytest.raises(EmbeddingUnavailableError):
                client.embed("t0")

        client._client.models.embed_content.assert_not_called()


class TestCreateBatch:
    def test_an_empty_batch_is_rejected_before_touching_the_quota(self):
        client = make_client()

        with patch.object(api_quota, "consume") as consume:
            with pytest.raises(EmbeddingError, match="empty"):
                client.create_batch([], display_name="x")

        consume.assert_not_called()

    def test_the_batch_is_created_with_the_expected_request(self):
        client = make_client(model="custom-model")
        client._client.batches.create_embeddings.return_value.name = "batches/123"

        name = client.create_batch(["a", "b"], display_name="nightly", cost=7)

        assert name == "batches/123"
        client._client.batches.create_embeddings.assert_called_once_with(
            model="custom-model",
            src={
                "inlined_requests": {
                    "contents": ["a", "b"],
                    "config": {"output_dimensionality": DIMENSIONS},
                }
            },
            config={"display_name": "nightly"},
        )

    def test_the_cost_defaults_to_the_sum_of_the_text_costs(self):
        client = make_client()

        with patch.object(api_quota, "text_cost", return_value=5), patch.object(
            api_quota, "consume"
        ) as consume:
            client.create_batch(["a", "b", "c"], display_name="x")

        consume.assert_called_once_with(QUOTA_BATCH, 15)

    def test_an_explicit_cost_is_used_as_is(self):
        client = make_client()

        with patch.object(api_quota, "text_cost") as text_cost, patch.object(
            api_quota, "consume"
        ) as consume:
            client.create_batch(["a"], display_name="x", cost=99)

        text_cost.assert_not_called()
        consume.assert_called_once_with(QUOTA_BATCH, 99)

    def test_a_failed_creation_refunds_the_quota(self):
        client = make_client()
        client._client.batches.create_embeddings.side_effect = FakeAPIError(500)

        with patch.object(api_quota, "consume"), patch.object(api_quota, "refund") as refund:
            with pytest.raises(
                EmbeddingUnavailableError, match="Could not create embedding batch"
            ) as info:
                client.create_batch(["a"], display_name="x", cost=12)

        refund.assert_called_once_with(QUOTA_BATCH, 12)
        assert isinstance(info.value.__cause__, APIError)

    def test_an_exhausted_quota_prevents_the_creation(self):
        client = make_client()

        with patch.object(
            api_quota, "consume", side_effect=api_quota.QuotaExceeded(QUOTA_BATCH, "day", 100)
        ), patch.object(api_quota, "refund") as refund:
            with pytest.raises(EmbeddingUnavailableError):
                client.create_batch(["a"], display_name="x", cost=1)

        client._client.batches.create_embeddings.assert_not_called()
        refund.assert_not_called()


def batch_item(values=None, *, error=None):
    item = MagicMock()
    item.error = error
    if values is None:
        item.response = None
    else:
        item.response.embedding.values = values
    return item


def batch_job(state_name, items=None, error=None):
    job = MagicMock()
    job.state.name = state_name
    job.error = error
    job.dest.inlined_embed_content_responses = items
    return job


class TestGetBatch:
    def test_the_batch_is_fetched_by_name(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job("JOB_STATE_RUNNING")

        client.get_batch("batches/1")

        client._client.batches.get.assert_called_once_with(name="batches/1")

    def test_api_errors_are_reported_as_unavailable(self):
        client = make_client()
        client._client.batches.get.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError, match="Could not fetch batch 'batches/1'"):
            client.get_batch("batches/1")

    def test_a_running_batch_has_no_embeddings(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job("JOB_STATE_RUNNING")

        result = client.get_batch("b")

        assert result.state == "JOB_STATE_RUNNING"
        assert result.error is None
        assert not result.embeddings

    def test_a_failed_batch_carries_its_error_text(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job("JOB_STATE_FAILED", error="boom")

        result = client.get_batch("b")

        assert result.state == "JOB_STATE_FAILED"
        assert result.error == "boom"
        assert not result.embeddings

    def test_a_missing_state_is_reported_as_unknown(self):
        client = make_client()
        job = batch_job("ignored")
        job.state = None
        client._client.batches.get.return_value = job

        assert client.get_batch("b").state == "UNKNOWN"

    def test_embeddings_are_normalised_and_keep_the_input_order(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job(
            "JOB_STATE_SUCCEEDED",
            [batch_item(one_hot(3)), batch_item([2.0] + [0.0] * (DIMENSIONS - 1))],
        )

        result = client.get_batch("b")

        assert [v.index(1.0) for v in result.embeddings] == [3, 0]
        assert result.item_errors == [None, None]

    def test_items_with_an_error_become_none_with_their_message(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job(
            "JOB_STATE_PARTIALLY_SUCCEEDED",
            [batch_item(one_hot(0)), batch_item(one_hot(1), error="quota"), batch_item(None)],
        )

        result = client.get_batch("b")

        assert result.embeddings[0] is not None
        assert result.embeddings[1:] == [None, None]
        assert result.item_errors == [None, "quota", "Missing embedding response."]

    def test_a_batch_without_responses_gives_empty_lists(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job("JOB_STATE_SUCCEEDED", None)

        result = client.get_batch("b")

        assert result.embeddings == []
        assert result.item_errors == []

    def test_vectors_with_too_few_dimensions_are_an_error(self):
        client = make_client()
        client._client.batches.get.return_value = batch_job(
            "JOB_STATE_SUCCEEDED", [batch_item([0.1, 0.2])]
        )

        with pytest.raises(EmbeddingError):
            client.get_batch("b")


class TestBatchStates:
    def test_result_states_are_a_subset_of_the_done_states(self):
        assert BATCH_RESULT_STATES <= BATCH_DONE_STATES

    def test_terminal_failures_are_done_but_have_no_results(self):
        failures = BATCH_DONE_STATES - BATCH_RESULT_STATES

        assert failures == {"JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}

    def test_running_states_are_not_done(self):
        assert "JOB_STATE_RUNNING" not in BATCH_DONE_STATES
        assert "JOB_STATE_PENDING" not in BATCH_DONE_STATES
