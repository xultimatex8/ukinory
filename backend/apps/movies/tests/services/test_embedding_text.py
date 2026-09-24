from __future__ import annotations

from apps.movies.services.embedding_text import build_embedding_text


def fake_metadata(**overrides) -> dict:
    metadata = {
        "title": "Blade Runner",
        "release_year": 1982,
        "wikidata_description": "1982 science fiction film directed by Ridley Scott",
        "genres": [
            {"wikidata_id": "Q471839", "name": "Science Fiction"},
            {"wikidata_id": "Q157394", "name": "Neo-noir"},
        ],
        "directors": ["Ridley Scott"],
        "original_language": "English",
        "runtime": 117,
    }
    metadata.update(overrides)
    return metadata


class TestBuildEmbeddingText:
    def test_includes_all_populated_fields(self):
        text = build_embedding_text(fake_metadata())

        assert "Blade Runner" in text
        assert "(1982)" in text
        assert "1982 science fiction film directed by Ridley Scott" in text
        assert "Genres: Neo-noir, Science Fiction" in text
        assert "Directed by: Ridley Scott" in text
        assert "Original language: English" in text
        assert "Runtime: 117 minutes" in text

    def test_genres_are_sorted_alphabetically_regardless_of_input_order(self):
        metadata = fake_metadata(
            genres=[
                {"wikidata_id": "Q1", "name": "Zombie"},
                {"wikidata_id": "Q2", "name": "Adventure"},
                {"wikidata_id": "Q3", "name": "Mystery"},
            ]
        )

        text = build_embedding_text(metadata)

        assert "Genres: Adventure, Mystery, Zombie" in text

    def test_directors_are_sorted_alphabetically_regardless_of_input_order(self):
        metadata = fake_metadata(directors=["Zack Snyder", "Ang Lee"])

        text = build_embedding_text(metadata)

        assert "Directed by: Ang Lee, Zack Snyder" in text

    def test_output_is_stable_across_input_orderings(self):
        metadata_a = fake_metadata(
            genres=[
                {"wikidata_id": "Q1", "name": "Drama"},
                {"wikidata_id": "Q2", "name": "Action"},
            ],
            directors=["B Director", "A Director"],
        )
        metadata_b = fake_metadata(
            genres=[
                {"wikidata_id": "Q2", "name": "Action"},
                {"wikidata_id": "Q1", "name": "Drama"},
            ],
            directors=["A Director", "B Director"],
        )

        assert build_embedding_text(metadata_a) == build_embedding_text(metadata_b)

    def test_missing_release_year_omits_parentheses(self):
        metadata = fake_metadata(release_year=None)

        text = build_embedding_text(metadata)

        assert "(" not in text
        assert "Blade Runner" in text

    def test_missing_optional_fields_are_omitted_without_empty_lines(self):
        metadata = fake_metadata(
            genres=[],
            directors=[],
            original_language="",
            runtime=None,
            wikidata_description="",
        )

        text = build_embedding_text(metadata)

        assert text == "Blade Runner\n(1982)"
        assert "Genres:" not in text
        assert "Directed by:" not in text
        assert "Original language:" not in text
        assert "Runtime:" not in text

    def test_missing_optional_keys_entirely_do_not_raise(self):
        minimal_metadata = {"title": "Some Movie"}

        text = build_embedding_text(minimal_metadata)

        assert text == "Some Movie"

    def test_empty_description_is_not_included_as_blank_line(self):
        metadata = fake_metadata(wikidata_description="")

        text = build_embedding_text(metadata)
        lines = text.split("\n")

        assert "" not in lines
