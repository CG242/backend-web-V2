from django.urls import path
from .views_analyse_auto import (
    declencher_analyse_auto,
    obtenir_resultats_analyse,
    obtenir_statistiques_donnees
)

app_name = 'analyse'

urlpatterns = [
    # Déclencher l'analyse automatique
    path('declencher/', declencher_analyse_auto, name='declencher_analyse'),
    
    # Obtenir les résultats de la dernière analyse
    path('resultats/', obtenir_resultats_analyse, name='resultats_analyse'),
    
    # Obtenir les statistiques des données récentes
    path('statistiques/', obtenir_statistiques_donnees, name='statistiques_donnees'),
]
