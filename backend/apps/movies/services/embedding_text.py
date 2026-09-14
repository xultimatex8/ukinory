from __future__ import annotations


def build_embedding_text(metadata: dict) -> str:
    parts = [
        metadata["title"],
        f"({metadata['release_year']})" if metadata.get("release_year") else "",
        metadata.get("wikidata_description", ""),
    ]

    genre_names = sorted(g["name"] for g in metadata.get("genres", []))
    if genre_names:
        parts.append("Genres: " + ", ".join(genre_names))

    directors = sorted(metadata.get("directors") or [])
    if directors:
        parts.append("Directed by: " + ", ".join(directors))

    if metadata.get("original_language"):
        parts.append(f"Original language: {metadata['original_language']}")

    if metadata.get("runtime"):
        parts.append(f"Runtime: {metadata['runtime']} minutes")

    return "\n".join(p for p in parts if p)
