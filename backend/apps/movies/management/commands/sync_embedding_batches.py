from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.movies.exceptions import EmbeddingError
from apps.movies.services.embedding_batch import (
    collect_finished_batches,
    submit_pending_embeddings_batch,
)
from config import settings


class Command(BaseCommand):
    help = (
        "Collects completed Gemini embedding batches and submits a new batch "
        "with the pending movies (respecting the quota)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--collect-only", action="store_true")
        parser.add_argument("--submit-only", action="store_true")
        parser.add_argument("--max-items", type=int, default=None)
        parser.add_argument("--min-items", type=int, default=1)

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "production":
            self.stdout.write(
                self.style.WARNING(
                    "Embedding batch sync skipped: environment is not production."
                )
            )
            return

        try:
            if not options["submit_only"]:
                summary = collect_finished_batches()
                self.stdout.write(f"Collect: {summary}")

            if not options["collect_only"]:
                job = submit_pending_embeddings_batch(
                    max_items=options["max_items"],
                    min_items=options["min_items"],
                )

                if job is None:
                    self.stdout.write("Submit: nothing submitted.")
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Submit: {job.job_name} ({len(job.items)} movies)."
                        )
                    )

        except EmbeddingError as exc:
            self.stderr.write(
                self.style.ERROR(f"Embedding batch sync failed: {exc}")
            )
            raise