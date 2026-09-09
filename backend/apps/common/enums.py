from django.db import models


class WatchlistSource(models.TextChoices):
    IMPORTED = "IMPORTED", "Imported"
    SWIPE_ADDED = "SWIPE_ADDED", "Swipe added"
    SWIPE_MATCH = "SWIPE_MATCH", "Swipe match"