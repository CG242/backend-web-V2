from django.apps import AppConfig


class ErosionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'erosion'
    
    def ready(self):
        import erosion.signals