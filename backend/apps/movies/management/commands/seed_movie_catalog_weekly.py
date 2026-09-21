from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.movies.exceptions import TMDbError, WikidataError
from apps.movies.services.catalog_seeding import format_seed_summary, seed_movie_catalog_deep
from config import settings


class Command(BaseCommand):
    help = (
        "Broad weekly sweep of the movie catalog across every decade "
        "(back to the 1900s) and every TMDb genre, enriched via Wikidata. "
        "Pair with seed_movie_catalog_daily for the cheap popular/new-"
        "release refresh in between."
    )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "production":
            self.stdout.write(
                self.style.WARNING(
                    "Catalog seeding (light) skipped: environment is not production."
                )
            )
            return
        
        try:
            summary = seed_movie_catalog_deep()
        except (TMDbError, WikidataError) as exc:
            self.stderr.write(self.style.ERROR(f"Catalog seeding (deep) failed: {exc}"))
            raise

        self.stdout.write(self.style.SUCCESS(format_seed_summary(summary)))