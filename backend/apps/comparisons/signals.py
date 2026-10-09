from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.comparisons.models import Comparison


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def delete_comparisons_of_deleted_user(sender, instance, **kwargs):
    Comparison.objects.filter(session__users=instance).delete()
