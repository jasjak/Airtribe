from django.apps import AppConfig


class IssuesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'issues'

    def ready(self):
        from .views import init_storage_files
        init_storage_files()
