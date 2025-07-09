# core/apps.py - ATUALIZADO

from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    # Adicione este método para importar os signals
    def ready(self):
        import core.signals