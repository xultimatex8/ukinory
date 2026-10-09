from django.apps import AppConfig


class ComparisonsConfig(AppConfig):
    name = "apps.comparisons"

    def ready(self) -> None:
        from apps.common.enums import InviteType
        from apps.comparisons import signals

