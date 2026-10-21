from django.apps import AppConfig


class ShohorCommonConfig(AppConfig):
    """Shared models every service gets: the event outbox."""

    name = "shohor_common"
    default_auto_field = "django.db.models.BigAutoField"
