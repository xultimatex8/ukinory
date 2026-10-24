from __future__ import annotations

import itertools
import math
from types import SimpleNamespace

import pytest

from apps.movies.models import Movie
from apps.recommendations.services.cf_propagation import (
    DEFAULT_PROPAGATION_K,
    propagate_cf_score,
)

DIMS = Movie._meta.get_field("embedding").dimensions
_tmdb_ids = itertools.count(920000)


def vec(*values):
    return [float(v) for v in values] + [0.0] * (DIMS - len(values))


def make_movie(title, embedding):
    return Movie.objects.create(
        tmdb_id=next(_tmdb_ids), title=title, release_year=2000, embedding=embedding
    )


class TestWithoutDatabase:
    def test_movie_without_embedding_gives_none(self):
        movie = SimpleNamespace(embedding=None)

        assert propagate_cf_score(movie, {1: 4.0}) is None

    def test_no_cf_scores_gives_none(self):
        movie = SimpleNamespace(embedding=vec(1, 0))

        assert propagate_cf_score(movie, {}) is None


@pytest.mark.django_db
class TestPropagateCfScore:
    def test_a_single_identical_neighbour_gives_its_score(self):
        target = make_movie("Target", vec(1, 0))
        neighbour = make_movie("Neighbour", vec(1, 0))

        assert propagate_cf_score(target, {neighbour.pk: 4.0}) == pytest.approx(4.0)

    def test_neighbours_are_weighted_by_similarity(self):
        target = make_movie("Target", vec(1, 0))
        close = make_movie("Close", vec(1, 0))
        diagonal = make_movie("Diagonal", vec(1, 1))

        score = propagate_cf_score(target, {close.pk: 5.0, diagonal.pk: 3.0})

        similarity = 1 / math.sqrt(2)
        expected = (1.0 * 5.0 + similarity * 3.0) / (1.0 + similarity)
        assert score == pytest.approx(expected, rel=1e-4)

    def test_dissimilar_neighbours_are_ignored(self):
        target = make_movie("Target", vec(1, 0))
        close = make_movie("Close", vec(1, 0))
        orthogonal = make_movie("Orthogonal", vec(0, 1))
        opposite = make_movie("Opposite", vec(-1, 0))

        score = propagate_cf_score(
            target, {close.pk: 4.0, orthogonal.pk: 1.0, opposite.pk: 1.0}
        )

        assert score == pytest.approx(4.0)

    def test_only_dissimilar_neighbours_gives_none(self):
        target = make_movie("Target", vec(1, 0))
        orthogonal = make_movie("Orthogonal", vec(0, 1))
        opposite = make_movie("Opposite", vec(-1, 0))

        assert (
            propagate_cf_score(target, {orthogonal.pk: 4.0, opposite.pk: 2.0}) is None
        )

    def test_only_films_with_a_cf_score_are_considered(self):
        target = make_movie("Target", vec(1, 0))
        scored = make_movie("Scored", vec(1, 1))
        make_movie("Unscored but identical", vec(1, 0))

        assert propagate_cf_score(target, {scored.pk: 2.0}) == pytest.approx(2.0)

    def test_scored_films_without_embedding_are_ignored(self):
        target = make_movie("Target", vec(1, 0))
        no_embedding = make_movie("No embedding", None)

        assert propagate_cf_score(target, {no_embedding.pk: 5.0}) is None

    def test_only_the_k_nearest_neighbours_are_used(self):
        target = make_movie("Target", vec(1, 0))
        nearest = make_movie("Nearest", vec(1, 0))
        farther = make_movie("Farther", vec(1, 1))

        score = propagate_cf_score(
            target, {nearest.pk: 5.0, farther.pk: 1.0}, k=1
        )

        assert score == pytest.approx(5.0)

    def test_default_k_limits_the_neighbours(self):
        target = make_movie("Target", vec(1, 0))
        scores = {}
        for i in range(DEFAULT_PROPAGATION_K):
            scores[make_movie(f"Near {i}", vec(1, 0.01 * i)).pk] = 5.0
        scores[make_movie("Far", vec(1, 5)).pk] = 1.0

        assert propagate_cf_score(target, scores) == pytest.approx(5.0)

    def test_nearer_neighbours_count_more_than_farther_ones(self):
        target = make_movie("Target", vec(1, 0))
        near = make_movie("Near", vec(1, 0.1))
        far = make_movie("Far", vec(1, 1))

        score = propagate_cf_score(target, {near.pk: 5.0, far.pk: 1.0})

        assert 3.0 < score < 5.0
