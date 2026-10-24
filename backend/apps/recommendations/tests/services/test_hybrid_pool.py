from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.common.enums import SwipeAction
from apps.recommendations.dtos.candidate import ScoredCandidate
from apps.recommendations.services.hybrid_pool import (
    ALPHA_MAX,
    ALPHA_MIN,
    AVG_SIMILARITY_FOR_FULL_TRUST,
    NEIGHBORS_FOR_FULL_TRUST,
    RATING_SCALE_MAX,
    SKIP_PENALTY_COOLDOWN_DAYS,
    SKIP_PENALTY_FULL_FADE_DAYS,
    SKIP_PENALTY_MAX,
    _adaptive_alpha,
    _skip_penalties,
    _sorted,
    build_hybrid_pool,
)

MODULE = "apps.recommendations.services.hybrid_pool"
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(id=7, pk=7)


def candidate(movie_id, similarity):
    return SimpleNamespace(movie=SimpleNamespace(id=movie_id), similarity=similarity)


def scored(final_score):
    return ScoredCandidate(SimpleNamespace(id=final_score), 0.0, None, False, final_score)


def users(count, similarity):
    return [(n, similarity) for n in range(count)]


class TestAdaptiveAlpha:
    def test_without_similar_users_content_gets_the_maximum_weight(self):
        assert _adaptive_alpha([]) == ALPHA_MAX

    def test_plenty_of_good_neighbours_give_the_minimum_weight(self):
        similar = users(NEIGHBORS_FOR_FULL_TRUST, AVG_SIMILARITY_FOR_FULL_TRUST)

        assert _adaptive_alpha(similar) == pytest.approx(ALPHA_MIN)

    def test_evidence_beyond_full_trust_does_not_lower_alpha_further(self):
        similar = users(NEIGHBORS_FOR_FULL_TRUST * 3, AVG_SIMILARITY_FOR_FULL_TRUST * 2)

        assert _adaptive_alpha(similar) == pytest.approx(ALPHA_MIN)

    def test_half_the_neighbours_give_half_the_trust(self):
        similar = users(NEIGHBORS_FOR_FULL_TRUST // 2, AVG_SIMILARITY_FOR_FULL_TRUST)

        expected = ALPHA_MAX - (ALPHA_MAX - ALPHA_MIN) * 0.5
        assert _adaptive_alpha(similar) == pytest.approx(expected)

    def test_half_the_similarity_gives_half_the_trust(self):
        similar = users(NEIGHBORS_FOR_FULL_TRUST, AVG_SIMILARITY_FOR_FULL_TRUST / 2)

        expected = ALPHA_MAX - (ALPHA_MAX - ALPHA_MIN) * 0.5
        assert _adaptive_alpha(similar) == pytest.approx(expected)

    def test_count_and_quality_multiply(self):
        similar = users(NEIGHBORS_FOR_FULL_TRUST // 2, AVG_SIMILARITY_FOR_FULL_TRUST / 2)

        expected = ALPHA_MAX - (ALPHA_MAX - ALPHA_MIN) * 0.25
        assert _adaptive_alpha(similar) == pytest.approx(expected)

    def test_more_neighbours_never_increase_alpha(self):
        alphas = [
            _adaptive_alpha(users(count, AVG_SIMILARITY_FOR_FULL_TRUST))
            for count in range(0, NEIGHBORS_FOR_FULL_TRUST + 3)
        ]

        assert alphas == sorted(alphas, reverse=True)

    def test_alpha_stays_within_its_bounds(self):
        for count in (1, 5, 50):
            for similarity in (0.01, 0.2, 0.9):
                assert ALPHA_MIN <= _adaptive_alpha(users(count, similarity)) <= ALPHA_MAX


class TestSorted:
    def test_orders_by_final_score_descending(self):
        results = [scored(0.2), scored(0.9), scored(0.5)]

        assert [c.final_score for c in _sorted(results)] == [0.9, 0.5, 0.2]

    def test_sorts_in_place_and_returns_the_same_list(self):
        results = [scored(0.1), scored(0.3)]

        assert _sorted(results) is results

    def test_empty_list(self):
        assert _sorted([]) == []


class TestSkipPenalties:
    @pytest.fixture(autouse=True)
    def frozen_now(self):
        with patch(f"{MODULE}.timezone.now", return_value=NOW):
            yield

    def _run(self, rows, movie_ids=frozenset({1})):
        with patch(f"{MODULE}.Swipe") as swipe:
            swipe.objects.filter.return_value.values.return_value.annotate.return_value = rows
            result = _skip_penalties(USER, set(movie_ids))
        return result, swipe

    def _row(self, movie_id, days_ago):
        return {
            "candidate__movie_id": movie_id,
            "last_skipped_at": NOW - timedelta(days=days_ago),
        }

    def test_no_candidates_means_no_query(self):
        with patch(f"{MODULE}.Swipe") as swipe:
            assert _skip_penalties(USER, set()) == {}

        swipe.objects.filter.assert_not_called()

    def test_queries_the_users_skips_of_the_given_films(self):
        _, swipe = self._run([], movie_ids={1, 2})

        swipe.objects.filter.assert_called_once_with(
            user=USER,
            action=SwipeAction.SKIP,
            candidate__movie_id__in={1, 2},
        )

    def test_films_that_were_never_skipped_have_no_entry(self):
        result, _ = self._run([])

        assert result == {}

    @pytest.mark.parametrize("days_ago", [0, 10, SKIP_PENALTY_COOLDOWN_DAYS])
    def test_recent_skips_get_the_full_penalty(self, days_ago):
        result, _ = self._run([self._row(1, days_ago)])

        assert result[1] == pytest.approx(1 - SKIP_PENALTY_MAX)

    def test_penalty_fades_linearly_after_the_cooldown(self):
        midpoint = (SKIP_PENALTY_COOLDOWN_DAYS + SKIP_PENALTY_FULL_FADE_DAYS) / 2

        result, _ = self._run([self._row(1, midpoint)])

        assert result[1] == pytest.approx(1 - SKIP_PENALTY_MAX / 2)

    @pytest.mark.parametrize(
        "days_ago", [SKIP_PENALTY_FULL_FADE_DAYS, SKIP_PENALTY_FULL_FADE_DAYS + 400]
    )
    def test_old_skips_have_no_penalty(self, days_ago):
        result, _ = self._run([self._row(1, days_ago)])

        assert result[1] == pytest.approx(1.0)

    def test_each_film_gets_its_own_penalty(self):
        result, _ = self._run(
            [self._row(1, 0), self._row(2, SKIP_PENALTY_FULL_FADE_DAYS)],
            movie_ids={1, 2},
        )

        assert result[1] < result[2]
        assert set(result) == {1, 2}


@pytest.fixture
def deps():
    names = [
        "build_candidate_pool",
        "_skip_penalties",
        "build_rating_matrix",
        "find_similar_users",
        "predict_cf_score",
        "propagate_cf_score",
    ]
    with ExitStack() as stack:
        mocks = SimpleNamespace(
            **{name: stack.enter_context(patch(f"{MODULE}.{name}")) for name in names}
        )
        mocks.build_candidate_pool.return_value = []
        mocks._skip_penalties.return_value = {}
        mocks.build_rating_matrix.return_value = SimpleNamespace(by_movie={})
        mocks.find_similar_users.return_value = []
        mocks.predict_cf_score.return_value = None
        mocks.propagate_cf_score.return_value = None
        yield mocks


class TestBuildHybridPool:
    def test_no_candidates_gives_an_empty_pool(self, deps):
        assert build_hybrid_pool(USER) == []

    def test_candidate_pool_is_built_with_the_requested_size(self, deps):
        build_hybrid_pool(USER, pool_size=5)

        deps.build_candidate_pool.assert_called_once_with(USER, pool_size=5)

    def test_skip_penalties_are_looked_up_for_the_candidate_films(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.5), candidate(2, 0.4)]

        build_hybrid_pool(USER)

        deps._skip_penalties.assert_called_once_with(USER, {1, 2})

    # ------------------------------------------------------------ content
    def test_content_strategy_uses_similarity_and_skip_penalty_only(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.8), candidate(2, 0.6)]
        deps._skip_penalties.return_value = {1: 0.5}

        result = build_hybrid_pool(USER, strategy="content")

        by_id = {c.movie.id: c for c in result}
        assert by_id[1].final_score == pytest.approx(0.4)
        assert by_id[2].final_score == pytest.approx(0.6)
        assert by_id[1].content_score == 0.8
        assert all(c.cf_score is None and c.cf_was_propagated is False for c in result)

    def test_content_strategy_does_not_touch_collaborative_filtering(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.8)]

        build_hybrid_pool(USER, strategy="content")

        deps.build_rating_matrix.assert_not_called()
        deps.find_similar_users.assert_not_called()
        deps.predict_cf_score.assert_not_called()

    def test_content_strategy_orders_by_penalised_score(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.9), candidate(2, 0.6)]
        deps._skip_penalties.return_value = {1: 0.5}

        result = build_hybrid_pool(USER, strategy="content")

        assert [c.movie.id for c in result] == [2, 1]

    # ------------------------------------------------------------- hybrid
    def test_hybrid_blends_content_and_direct_cf(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.6)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 4.0

        result = build_hybrid_pool(USER, alpha=0.5)

        item = result[0]
        assert item.cf_score == pytest.approx(4.0 / RATING_SCALE_MAX)
        assert item.cf_was_propagated is False
        assert item.content_score == 0.6
        assert item.final_score == pytest.approx(0.5 * 0.6 + 0.5 * 0.8)

    def test_hybrid_propagates_cf_to_films_without_direct_scores(self, deps):
        movie_candidate = candidate(2, 0.6)
        deps.build_candidate_pool.return_value = [movie_candidate]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 5.0
        deps.propagate_cf_score.return_value = 3.0

        result = build_hybrid_pool(USER, alpha=0.5)

        item = result[0]
        assert item.cf_was_propagated is True
        assert item.cf_score == pytest.approx(3.0 / RATING_SCALE_MAX)
        deps.propagate_cf_score.assert_called_once_with(
            movie_candidate.movie, {1: 5.0}
        )
        assert item.final_score == pytest.approx(0.5 * 0.6 + 0.5 * 0.6)

    def test_hybrid_without_any_cf_signal_falls_back_to_content_similarity(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.7)]

        item = build_hybrid_pool(USER, alpha=0.3)[0]

        assert item.cf_score is None
        assert item.final_score == pytest.approx(0.7)

    def test_direct_scores_are_only_collected_for_films_with_a_prediction(self, deps):
        deps.build_candidate_pool.return_value = [candidate(9, 0.5)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}, 2: {}, 3: {}})
        deps.predict_cf_score.side_effect = lambda movie_id, matrix, similar: {
            1: 4.0, 2: None, 3: 2.5,
        }[movie_id]

        build_hybrid_pool(USER)

        assert deps.propagate_cf_score.call_args.args[1] == {1: 4.0, 3: 2.5}

    def test_similar_users_come_from_the_rating_matrix(self, deps):
        matrix = SimpleNamespace(by_movie={})
        deps.build_rating_matrix.return_value = matrix
        deps.find_similar_users.return_value = [(3, 0.9)]
        deps.build_candidate_pool.return_value = [candidate(1, 0.5)]

        with patch(f"{MODULE}._adaptive_alpha", return_value=0.5):
            build_hybrid_pool(USER)

        deps.find_similar_users.assert_called_once_with(USER.id, matrix)

    def test_alpha_is_adaptive_when_not_given(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.6)]
        deps.find_similar_users.return_value = [(3, 0.9)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 5.0

        with patch(f"{MODULE}._adaptive_alpha", return_value=0.4) as adaptive:
            item = build_hybrid_pool(USER)[0]

        adaptive.assert_called_once_with([(3, 0.9)])
        assert item.final_score == pytest.approx(0.4 * 0.6 + 0.6 * 1.0)

    def test_an_explicit_alpha_overrides_the_adaptive_one(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.6)]

        with patch(f"{MODULE}._adaptive_alpha") as adaptive:
            build_hybrid_pool(USER, alpha=0.9)

        adaptive.assert_not_called()

    def test_alpha_zero_is_respected(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.6)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 5.0

        item = build_hybrid_pool(USER, alpha=0.0)[0]

        assert item.final_score == pytest.approx(1.0)

    def test_skip_penalty_scales_the_hybrid_score(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.6)]
        deps._skip_penalties.return_value = {1: 0.5}

        item = build_hybrid_pool(USER, alpha=0.5)[0]

        assert item.final_score == pytest.approx(0.6 * 0.5)

    def test_hybrid_results_are_sorted_by_final_score(self, deps):
        deps.build_candidate_pool.return_value = [
            candidate(1, 0.2), candidate(2, 0.9), candidate(3, 0.5),
        ]

        result = build_hybrid_pool(USER, alpha=0.5)

        assert [c.movie.id for c in result] == [2, 3, 1]

    # ------------------------------------------------------ collaborative
    def test_collaborative_strategy_ignores_content_and_alpha(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.99)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 2.5

        item = build_hybrid_pool(USER, strategy="collaborative", alpha=0.9)[0]

        assert item.final_score == pytest.approx(0.5)
        assert item.content_score == 0.99

    def test_collaborative_strategy_scores_zero_without_cf(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.99)]

        item = build_hybrid_pool(USER, strategy="collaborative")[0]

        assert item.final_score == 0.0
        assert item.cf_score is None

    def test_collaborative_strategy_applies_skip_penalties(self, deps):
        deps.build_candidate_pool.return_value = [candidate(1, 0.5)]
        deps.build_rating_matrix.return_value = SimpleNamespace(by_movie={1: {}})
        deps.predict_cf_score.return_value = 5.0
        deps._skip_penalties.return_value = {1: 0.7}

        item = build_hybrid_pool(USER, strategy="collaborative")[0]

        assert item.final_score == pytest.approx(0.7)
