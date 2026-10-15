from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "submissions"

    def ready(self):
        from projects.signals import project_abandoned, project_takedown
        from submissions import ari, services
        project_abandoned.connect(ari.withdraw_if_open, dispatch_uid="ari_withdraw_if_open")
        project_takedown.connect(services.take_down_project, dispatch_uid="take_down_project")
