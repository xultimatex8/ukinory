from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_DISPATCH_TIMEOUT_SECONDS = 5


def trigger_import_worker() -> None:
    if settings.DEBUG:
        logger.debug(
            "Skipping GitHub workflow dispatch: DEBUG is True. The import "
            "job was still enqueued -- run `python manage.py rqworker "
            "default` locally to process it."
        )
        return

    token = getattr(settings, "GITHUB_DISPATCH_TOKEN", None)
    repo = getattr(settings, "GITHUB_REPO", None)
    workflow_file = getattr(settings, "GITHUB_WORKFLOW_FILE", "process-imports.yml")
    ref = getattr(settings, "GITHUB_DISPATCH_REF", "main")

    if not token or not repo:
        logger.info(
            "GITHUB_DISPATCH_TOKEN/GITHUB_REPO not configured; the import "
            "will be picked up by the hourly scheduled workflow instead."
        )
        return

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"ref": ref},
            timeout=_DISPATCH_TIMEOUT_SECONDS,
        )
        if not response.ok:
            logger.warning(
                "GitHub workflow dispatch failed (%s): %s",
                response.status_code, response.text[:300],
            )
    except requests.RequestException:
        logger.warning("GitHub workflow dispatch request failed.", exc_info=True)
