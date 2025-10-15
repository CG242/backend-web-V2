"""
Vues pour l'analyse automatique des données capteurs
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from .models import CapteurArduino, MesureArduino, Zone, EvenementExterne, FusionDonnees, PredictionEnrichie, AlerteEnrichie
from .services_analyse_auto import analyse_service
from .services_analyse_capteurs import analyse_capteurs_service

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def declencher_analyse_auto(request):
    """
    Déclenche l'analyse automatique des données capteurs
    POST /api/analyse-auto/declencher/
    """
    try:
        capteur_id = request.data.get('capteur_id')
        type_analyse = request.data.get('type', 'capteurs')  # 'capteurs' ou 'complet'
        
        logger.info(f"🔍 Déclenchement de l'analyse automatique (capteur_id: {capteur_id}, type: {type_analyse})")
        
        # Déclencher l'analyse selon le type
        if type_analyse == 'capteurs':
            resultat = analyse_capteurs_service.analyser_mesures_capteurs(capteur_id)
        else:
            resultat = analyse_service.analyser_nouvelles_donnees(capteur_id)
        
        if resultat['success']:
            return Response({
                'success': True,
                'message': f'Analyse {type_analyse} terminée avec succès',
                'zones_analysees': resultat['zones_analysees'],
                'alertes_generees': resultat['alertes_generees'],
                'resultats': resultat['resultats'],
                'alertes': resultat['alertes'],
                'timestamp': str(timezone.now())
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': resultat['message'],
                'timestamp': str(timezone.now())
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"❌ Erreur lors du déclenchement de l'analyse: {e}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}',
            'timestamp': str(timezone.now())
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def obtenir_resultats_analyse(request):
    """
    Obtient les résultats de la dernière analyse automatique
    GET /api/analyse-auto/resultats/
    """
    try:
        # Récupérer les dernières fusions de données
        fusions_recentes = FusionDonnees.objects.filter(
            statut='terminee',
            date_creation__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-date_creation')[:10]
        
        # Récupérer les dernières prédictions enrichies
        predictions_recentes = PredictionEnrichie.objects.filter(
            date_prediction__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-date_prediction')[:10]
        
        # Récupérer les alertes actives
        alertes_actives = AlerteEnrichie.objects.filter(
            est_active=True,
            date_creation__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-date_creation')[:10]
        
        resultats = []
        for fusion in fusions_recentes:
            # Chercher la prédiction correspondante
            prediction = None
            for pred in predictions_recentes:
                if pred.fusion_donnees_id == fusion.id:
                    prediction = pred
                    break
            
            # Chercher l'alerte correspondante
            alerte = None
            for alert in alertes_actives:
                if alert.zone_id == fusion.zone_id:
                    alerte = alert
                    break
            
            resultats.append({
                'zone_id': fusion.zone.id,
                'zone_nom': fusion.zone.nom,
                'fusion_id': fusion.id,
                'score_erosion': fusion.score_erosion,
                'probabilite_erosion': fusion.probabilite_erosion,
                'facteurs_dominants': fusion.facteurs_dominants,
                'date_analyse': fusion.date_creation,
                'prediction': {
                    'id': prediction.id if prediction else None,
                    'erosion_predite': prediction.erosion_predite if prediction else None,
                    'niveau_erosion': prediction.niveau_erosion if prediction else None,
                    'confiance_pourcentage': prediction.confiance_pourcentage if prediction else None,
                    'recommandations': prediction.recommandations if prediction else []
                } if prediction else None,
                'alerte': {
                    'id': alerte.id if alerte else None,
                    'niveau': alerte.niveau if alerte else None,
                    'titre': alerte.titre if alerte else None,
                    'est_active': alerte.est_active if alerte else None
                } if alerte else None
            })
        
        return Response({
            'success': True,
            'message': f'{len(resultats)} analyses récentes trouvées',
            'resultats': resultats,
            'timestamp': str(timezone.now())
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des résultats: {e}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}',
            'timestamp': str(timezone.now())
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def obtenir_statistiques_donnees(request):
    """
    Obtient les statistiques des données récentes
    GET /api/analyse-auto/statistiques/
    """
    try:
        # Période de 24 heures
        depuis = timezone.now() - timedelta(hours=24)
        
        # Statistiques des capteurs
        capteurs_actifs = CapteurArduino.objects.filter(actif=True).count()
        mesures_recentes = MesureArduino.objects.filter(
            timestamp__gte=depuis,
            est_valide=True
        ).count()
        
        # Statistiques par zone
        zones_stats = []
        zones = Zone.objects.all()
        
        for zone in zones:
            capteurs_zone = CapteurArduino.objects.filter(zone=zone, actif=True)
            mesures_zone = MesureArduino.objects.filter(
                capteur__zone=zone,
                timestamp__gte=depuis,
                est_valide=True
            )
            evenements_zone = EvenementExterne.objects.filter(
                zone=zone,
                date_evenement__gte=depuis,
                is_valide=True
            )
            
            zones_stats.append({
                'zone_id': zone.id,
                'zone_nom': zone.nom,
                'capteurs_actifs': capteurs_zone.count(),
                'mesures_24h': mesures_zone.count(),
                'evenements_24h': evenements_zone.count(),
                'derniere_mesure': mesures_zone.order_by('-timestamp').first().timestamp if mesures_zone.exists() else None
            })
        
        # Statistiques des événements
        evenements_recentes = EvenementExterne.objects.filter(
            date_evenement__gte=depuis,
            is_valide=True
        ).count()
        
        # Alertes actives
        alertes_actives = AlerteEnrichie.objects.filter(
            est_active=True
        ).count()
        
        return Response({
            'success': True,
            'message': 'Statistiques récupérées avec succès',
            'statistiques': {
                'periode': '24 dernières heures',
                'capteurs_actifs': capteurs_actifs,
                'mesures_recentes': mesures_recentes,
                'evenements_recentes': evenements_recentes,
                'alertes_actives': alertes_actives,
                'zones': zones_stats
            },
            'timestamp': str(timezone.now())
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des statistiques: {e}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}',
            'timestamp': str(timezone.now())
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
