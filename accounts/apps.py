from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        """
        Import signal handlers so they are registered when the app starts.
        This is the recommended Django pattern for signal registration.
        Requirements: 1.1, 1.2
        """
        import accounts.signals  # noqa: F401
