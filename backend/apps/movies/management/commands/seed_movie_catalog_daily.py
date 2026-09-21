from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.movies.exceptions import TMDbError, WikidataError
from apps.movies.services.catalog_seeding import format_seed_summary, seed_movie_catalog_light
from django.conf import settings


class Command(BaseCommand):
    help = (
        "Cheap daily refresh of the movie catalog: TMDb's popular titles "
        "and recently released titles, enriched via "
        "Wikidata. For the broader per-decade/per-genre sweep, run "
        "seed_movie_catalog_weekly instead."
    )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "production":
            self.stdout.write(
                self.style.WARNING(
                    "Catalog seeding (deep) skipped: environment is not production."
                )
            )
            return
        
        try:
            summary = seed_movie_catalog_light()
        except (TMDbError, WikidataError) as exc:
            self.stderr.write(self.style.ERROR(f"Catalog seeding (light) failed: {exc}"))
            raise

        self.stdout.write(self.style.SUCCESS(format_seed_summary(summary)))
