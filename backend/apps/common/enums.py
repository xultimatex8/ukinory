from django.db import models


class WatchlistSource(models.TextChoices):
    IMPORTED = "IMPORTED", "Imported"
    SWIPE_ADDED = "SWIPE_ADDED", "Swipe added"
    SWIPE_MATCH = "SWIPE_MATCH", "Swipe match"


class SwipeAction(models.TextChoices):
    SKIP = "SKIP", "Skip"
    WATCHLIST = "WATCHLIST", "Added to watchlist"


class SwipeSessionType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Individual"
    PAIRED = "PAIRED", "Paired"


class SwipeSessionStatus(models.TextChoices):
    WAITING = "WAITING", "Waiting"
    ACTIVE = "ACTIVE", "Active"
    FINISHED = "FINISHED", "Finished"
