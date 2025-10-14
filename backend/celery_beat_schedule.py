from celery.schedules import crontab
from celery import Celery

# Configuration des tâches périodiques Celery
CELERY_BEAT_SCHEDULE = {
    # Générer des mesures automatiques toutes les 5 minutes
    'generer-mesures-automatiques': {
        'task': 'erosion.tasks.generer_mesures_automatiques',
        'schedule': crontab(minute='*/5'),  # Toutes les 5 minutes
    },
    
    # Vérifier l'état des capteurs toutes les heures
    'verifier-etat-capteurs': {
        'task': 'erosion.tasks.verifier_etat_capteurs',
        'schedule': crontab(minute=0),  # Toutes les heures
    },
    
    # Nettoyer les anciennes mesures tous les jours à 2h du matin
    'nettoyer-anciennes-mesures': {
        'task': 'erosion.tasks.nettoyer_anciennes_mesures',
        'schedule': crontab(hour=2, minute=0),  # Tous les jours à 2h
    },
    
    # ============================================================================
    # NOUVELLES TÂCHES POUR ÉVÉNEMENTS EXTERNES ET FUSION DE DONNÉES
    # ============================================================================
    
    # Traiter les événements en attente toutes les heures
    'traiter-evenements-en-attente': {
        'task': 'erosion.tasks.traiter_evenements_en_attente',
        'schedule': crontab(minute=0),  # Toutes les heures
    },
    
    # Nettoyer les anciens événements tous les jours à 3h du matin
    'nettoyer-anciens-evenements': {
        'task': 'erosion.tasks.nettoyer_anciens_evenements',
        'schedule': crontab(hour=3, minute=0),  # Tous les jours à 3h
    },
    
    # Nettoyer les anciennes fusions tous les jours à 4h du matin
    'nettoyer-anciennes-fusions': {
        'task': 'erosion.tasks.nettoyer_anciennes_fusions',
        'schedule': crontab(hour=4, minute=0),  # Tous les jours à 4h
    },
    
    # Nettoyer les anciennes prédictions tous les jours à 5h du matin
    'nettoyer-anciennes-predictions': {
        'task': 'erosion.tasks.nettoyer_anciennes_predictions',
        'schedule': crontab(hour=5, minute=0),  # Tous les jours à 5h
    },
    
    # Nettoyer les anciennes alertes tous les jours à 6h du matin
    'nettoyer-anciennes-alertes': {
        'task': 'erosion.tasks.nettoyer_anciennes_alertes',
        'schedule': crontab(hour=6, minute=0),  # Tous les jours à 6h
    },
    
    # Générer le rapport de fusion quotidien tous les jours à 7h du matin
    'generer-rapport-fusion-quotidien': {
        'task': 'erosion.tasks.generer_rapport_fusion_quotidien',
        'schedule': crontab(hour=7, minute=0),  # Tous les jours à 7h
    },
    
    # Exporter les données pour l'IA toutes les semaines (dimanche à 8h)
    'exporter-donnees-ia': {
        'task': 'erosion.tasks.exporter_donnees_ia',
        'schedule': crontab(hour=8, minute=0, day_of_week=0),  # Dimanche à 8h
    },
    
    # Purger les anciennes archives tous les mois (1er du mois à 9h)
    'purger-anciennes-archives': {
        'task': 'erosion.tasks.purger_anciennes_archives',
        'schedule': crontab(hour=9, minute=0, day_of_month=1),  # 1er du mois à 9h
    },
}
