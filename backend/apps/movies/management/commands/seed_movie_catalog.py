from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.movies.exceptions import TMDbError, WikidataError
from apps.movies.services.catalog_seeding import format_seed_summary, seed_movie_catalog


class Command(BaseCommand):
    help = (
        "Full seed/refresh of the movie catalog: every discovery angle "
        "(popular, new release, by-decade, by-genre) in a single run, "
        "enriched via Wikidata. Prefer seed_movie_catalog_daily + "
        "seed_movie_catalog_weekly for the ongoing recurring schedule."
    )

    def handle(self, *args, **options):
        try:
            summary = seed_movie_catalog()
        except (TMDbError, WikidataError) as exc:
            self.stderr.write(self.style.ERROR(f"Catalog seeding failed: {exc}"))
            raise

        self.stdout.write(self.style.SUCCESS(format_seed_summary(summary)))
