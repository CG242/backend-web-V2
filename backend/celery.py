from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Configuration Django pour Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('erosion_backend')

# Configuration Celery depuis Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches
app.autodiscover_tasks()

# Configuration des tâches périodiques
app.conf.beat_schedule = {
    # Tâches existantes
    'generer-mesures-automatiques': {
        'task': 'erosion.tasks.generer_mesures_automatiques',
        'schedule': crontab(minute='*/5'),  # Toutes les 5 minutes
    },
    'verifier-etat-capteurs': {
        'task': 'erosion.tasks.verifier_etat_capteurs',
        'schedule': crontab(minute=0, hour='*/1'),  # Toutes les heures
    },
    'nettoyer-anciennes-mesures': {
        'task': 'erosion.tasks.nettoyer_anciennes_mesures',
        'schedule': crontab(minute=0, hour=2),  # Tous les jours à 2h
    },
    
    # Nouvelles tâches pour les fonctionnalités enrichies
    'collecter-donnees-environnementales': {
        'task': 'erosion.tasks.collecter_donnees_environnementales',
        'schedule': crontab(minute=0, hour='*/6'),  # Toutes les 6 heures
    },
    'generer-analyses-erosion-automatiques': {
        'task': 'erosion.tasks.generer_analyses_erosion_automatiques',
        'schedule': crontab(minute=30, hour='*/12'),  # Toutes les 12 heures
    },
    'nettoyer-donnees-anciennes': {
        'task': 'erosion.tasks.nettoyer_donnees_anciennes',
        'schedule': crontab(minute=0, hour=3),  # Tous les jours à 3h
    },
    'synchroniser-donnees-cartographiques': {
        'task': 'erosion.tasks.synchroniser_donnees_cartographiques',
        'schedule': crontab(minute=0, hour=4),  # Tous les jours à 4h
    },
    'generer-rapport-quotidien': {
        'task': 'erosion.tasks.generer_rapport_quotidien',
        'schedule': crontab(minute=0, hour=6),  # Tous les jours à 6h
    },
    
    # Nouvelles tâches pour les capteurs Arduino
    'monitorer-capteurs-arduino': {
        'task': 'erosion.tasks.monitorer_capteurs_arduino',
        'schedule': crontab(minute='*/10'),  # Toutes les 10 minutes
    },
    'detecter-donnees-manquantes-arduino': {
        'task': 'erosion.tasks.detecter_donnees_manquantes_arduino',
        'schedule': crontab(minute='*/30'),  # Toutes les 30 minutes
    },
    'completer-donnees-manquantes-arduino': {
        'task': 'erosion.tasks.completer_donnees_manquantes_arduino',
        'schedule': crontab(minute=0, hour='*/2'),  # Toutes les 2 heures
    },
    'nettoyer-anciennes-mesures-arduino': {
        'task': 'erosion.tasks.nettoyer_anciennes_mesures_arduino',
        'schedule': crontab(minute=0, hour=1),  # Tous les jours à 1h
    },
    'generer-rapport-arduino-quotidien': {
        'task': 'erosion.tasks.generer_rapport_arduino_quotidien',
        'schedule': crontab(minute=0, hour=7),  # Tous les jours à 7h
    },
    'detecter-capteurs-automatique': {
        'task': 'erosion.tasks.detecter_capteurs_automatique',
        'schedule': crontab(minute='*/5'),  # Toutes les 5 minutes
    },
    'envoyer-notifications-quotidiennes': {
        'task': 'erosion.tasks.envoyer_notifications_quotidiennes',
        'schedule': crontab(minute=0, hour=8),  # Tous les jours à 8h
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
