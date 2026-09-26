from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.imports.models import ImportJob, ImportJobStatus

STALE_AFTER = timedelta(hours=2)


class Command(BaseCommand):
    help = "Marks stale import jobs as failed and deletes their associated files."

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_AFTER

        stale_jobs = ImportJob.objects.filter(
            status__in=[ImportJobStatus.PENDING, ImportJobStatus.RUNNING],
            created_at__lt=cutoff,
        )

        stale_job_list = list(stale_jobs)
        if not stale_job_list:
            self.stdout.write("No stale import jobs found.")
            return

        self.stdout.write(f"Found {len(stale_job_list)} stale import jobs:")
        for job in stale_job_list:
            self.stdout.write(
                f"  - {job.pk} (status={job.status}, created_at={job.created_at})"
            )

        for job in stale_job_list:
            job.mark_failed(
                "Import timed out or worker never completed the job."
            )
            job.files.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Marked {len(stale_job_list)} stale import jobs as failed."
            )
        )
        self.stdout.write(
            f"Deleted files associated with {len(stale_job_list)} stale import jobs."
        )
