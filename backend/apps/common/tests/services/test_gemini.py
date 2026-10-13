from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.common import api_quota
from apps.common.services.gemini import AIUnavailableError, Completion, GeminiClient


class DummyClient(GeminiClient):
    quota_name = "gemini_test"


def _response(text="hello", *, prompt_tokens=7):
    response = MagicMock()
    response.text = text
    response.usage_metadata.prompt_token_count = prompt_tokens
    response.usage_metadata.candidates_token_count = 3
    response.usage_metadata.thoughts_token_count = 0
    response.candidates = [MagicMock(finish_reason="STOP")]
    return response


@pytest.fixture
def quota():
    with patch.object(api_quota, "estimate_tokens", return_value=10), \
         patch.object(api_quota, "cost_units", side_effect=[10, 4]) as cost_units, \
         patch.object(api_quota, "consume") as consume, \
         patch.object(api_quota, "adjust") as adjust:
        yield MagicMock(cost_units=cost_units, consume=consume, adjust=adjust)


@pytest.fixture
def genai_client():
    with patch("apps.common.services.gemini.genai.Client") as client_cls:
        yield client_cls.return_value.models


class TestComplete:
    def test_returns_completion_and_reconciles_cost(self, quota, genai_client):
        genai_client.generate_content.return_value = _response("  hello  ")

        result = DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

        assert result == Completion(text="hello", finish_reason="STOP")
        quota.consume.assert_called_once_with("gemini_test", 10)
        quota.adjust.assert_called_once_with("gemini_test", -6)

    def test_json_output_sets_mime_type(self, quota, genai_client):
        genai_client.generate_content.return_value = _response("{}")

        DummyClient(api_key="k").complete(
            "prompt", max_output_tokens=50, json_output=True
        )

        config = genai_client.generate_content.call_args.kwargs["config"]
        assert config.response_mime_type == "application/json"

    def test_plain_output_has_no_mime_type(self, quota, genai_client):
        genai_client.generate_content.return_value = _response()

        DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

        config = genai_client.generate_content.call_args.kwargs["config"]
        assert config.response_mime_type is None

    def test_quota_exceeded_raises_without_calling_provider(self, quota, genai_client):
        quota.consume.side_effect = api_quota.QuotaExceeded("gemini_test", "day", 10)

        with pytest.raises(AIUnavailableError):
            DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

        genai_client.generate_content.assert_not_called()

    def test_provider_error_raises(self, quota, genai_client):
        genai_client.generate_content.side_effect = RuntimeError("boom")

        with pytest.raises(AIUnavailableError):
            DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

    def test_empty_answer_raises_but_still_reconciles_cost(self, quota, genai_client):
        genai_client.generate_content.return_value = _response("   ")

        with pytest.raises(AIUnavailableError):
            DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

        quota.adjust.assert_called_once()

    def test_reconcile_failure_does_not_fail_the_call(self, quota, genai_client):
        genai_client.generate_content.return_value = _response("ok")
        quota.adjust.side_effect = RuntimeError("redis down")

        result = DummyClient(api_key="k").complete("prompt", max_output_tokens=50)

        assert result.text == "ok"

    def test_subclass_without_quota_name_is_rejected(self, genai_client):
        with pytest.raises(NotImplementedError):
            GeminiClient(api_key="k").complete("prompt", max_output_tokens=50)
