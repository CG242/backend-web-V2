"""
Vues pour l'envoi d'alertes au format spécifié
"""
import logging
import json
import requests
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import AlerteEnrichie, Zone

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def test_frontend_endpoint(request):
    """
    Endpoint de test pour simuler le frontend
    POST /alertes/
    """
    try:
        # Récupérer l'alerte_id depuis POST ou JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            alerte_id = data.get('alerte_id')
        else:
            alerte_id = request.POST.get('alerte_id')
        
        if not alerte_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de l\'alerte requis'
            }, status=400)
        
        # Récupérer l'alerte
        try:
            alerte = AlerteEnrichie.objects.get(id=alerte_id)
        except AlerteEnrichie.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Alerte introuvable'
            }, status=404)
        
        # Simuler la réception de l'alerte par le frontend
        logger.info(f"Frontend simulé a reçu l'alerte {alerte.id}: {alerte.titre}")
        
        return JsonResponse({
            'success': True,
            'message': f'Alerte {alerte.id} reçue par le frontend simulé',
            'alerte_id': alerte.id,
            'titre': alerte.titre,
            'niveau': alerte.niveau,
            'received': True
        }, status=200)
        
    except Exception as e:
        logger.error(f"Erreur dans l'endpoint de test frontend: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def envoyer_alerte_externe(request):
    """
    Envoie une alerte au système externe au format spécifié
    POST /api/alertes/
    """
    try:
        # Récupérer l'alerte_id depuis POST ou JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            alerte_id = data.get('alerte_id')
            destination = data.get('destination', 'externe')
        else:
            alerte_id = request.POST.get('alerte_id')
            destination = request.POST.get('destination', 'externe')
        
        if not alerte_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de l\'alerte requis'
            }, status=400)
        
        # Récupérer l'alerte
        try:
            alerte = AlerteEnrichie.objects.get(id=alerte_id)
        except AlerteEnrichie.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Alerte introuvable'
            }, status=404)
        
        # Extraire les coordonnées de la zone (centre du polygone)
        latitude = None
        longitude = None
        if alerte.zone and alerte.zone.geometrie:
            try:
                # Calculer le centroïde de la zone
                centroid = alerte.zone.geometrie.centroid
                latitude = float(centroid.y)
                longitude = float(centroid.x)
            except Exception as e:
                logger.warning(f"Impossible d'extraire les coordonnées de la zone {alerte.zone.id}: {e}")
        
        # Préparer les données au format SQL spécifié avec TOUTES les données
        donnees_alerte = {
            'id_alerte': alerte.id,
            'titre': alerte.titre,
            'description': alerte.description,
            'niveau_urgence': alerte.niveau,  # 'faible', 'modéré', 'élevé', 'critique'
            'latitude': latitude,  # DECIMAL(10, 8) - Coordonnées extraites de la zone
            'longitude': longitude,  # DECIMAL(11, 8) - Coordonnées extraites de la zone
            'zone': alerte.zone.nom,  # VARCHAR(255)
            'date_creation': alerte.date_creation.isoformat(),  # TIMESTAMPTZ
            'date_mise_a_jour': alerte.date_resolution.isoformat() if alerte.date_resolution else alerte.date_creation.isoformat(),  # TIMESTAMPTZ
            'statut': 'active' if alerte.est_active else 'resolue',  # 'active', 'resolue', 'archivée'
            'source': 'système_erosion',  # VARCHAR(100)
            'donnees_meteo': alerte.donnees_contexte.get('meteo', {}),  # JSONB
            'donnees_marines': alerte.donnees_contexte.get('marines', {}),  # JSONB
            
            # Données supplémentaires de l'alerte enrichie
            'type': alerte.type,
            'est_active': alerte.est_active,
            'est_resolue': alerte.est_resolue,
            'date_resolution': alerte.date_resolution.isoformat() if alerte.date_resolution else None,
            'actions_requises': alerte.actions_requises,
            'donnees_contexte': alerte.donnees_contexte,
            
            # Informations sur la zone
            'zone_id': alerte.zone.id,
            'zone_description': getattr(alerte.zone, 'description', ''),
            'zone_type': getattr(alerte.zone, 'type_zone', ''),
            
            # Informations sur la prédiction si disponible
            'prediction_id': alerte.prediction_enrichie.id if alerte.prediction_enrichie else None,
            'evenement_id': alerte.evenement_externe.id if alerte.evenement_externe else None,
        }
        
        # Déterminer la destination
        if destination == 'frontend':
            # URL du frontend (configurable)
            url_frontend = getattr(settings, 'FRONTEND_URL', 'http://192.168.100.168:3000/api/alertes')
            url_destination = url_frontend
            destination_name = "frontend"
        else:
            # URL du système externe (configurable)
            url_externe = getattr(settings, 'ALERTE_EXTERNE_URL', 'http://192.168.100.168:8000/api/alertes')
            url_destination = url_externe
            destination_name = "système externe"
        
        # Envoyer l'alerte
        try:
            logger.info(f"=== DÉBUT ENVOI ALERTE {alerte.id} ===")
            logger.info(f"Destination: {destination_name}")
            logger.info(f"URL complète: {url_destination}")
            logger.info(f"Headers: {{'Content-Type': 'application/json'}}")
            logger.info(f"Timeout: 5 secondes")
            logger.info(f"Données à envoyer:")
            logger.info(json.dumps(donnees_alerte, indent=2, ensure_ascii=False))
            
            # Test de connectivité avant l'envoi
            logger.info(f"Test de connectivité vers {url_destination}...")
            
            response = requests.post(
                url_destination,
                json=donnees_alerte,
                headers={'Content-Type': 'application/json'},
                timeout=10  # Timeout augmenté
            )
            
            logger.info(f"=== RÉPONSE REÇUE ===")
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Headers de réponse: {dict(response.headers)}")
            logger.info(f"Taille de la réponse: {len(response.content)} bytes")
            logger.info(f"Contenu de la réponse: {response.text[:1000]}...")
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ SUCCÈS: Alerte {alerte.id} envoyée avec succès au {destination_name}")
                return JsonResponse({
                    'success': True,
                    'message': f'Alerte envoyée',
                    'alerte_id': alerte.id,
                    'titre': alerte.titre,
                    'niveau': alerte.niveau,
                    'destination': destination_name,
                    'sent': True
                }, status=200)
            else:
                logger.error(f"❌ ERREUR: Status {response.status_code} lors de l'envoi de l'alerte {alerte.id} au {destination_name}")
                logger.error(f"Détails de l'erreur: {response.text[:500]}")
                return JsonResponse({
                    'success': False,
                    'message': f'Erreur lors de l\'envoi au {destination_name}: {response.status_code}',
                    'details': response.text[:500]  # Limiter la taille de la réponse
                }, status=400)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"=== ERREUR DE CONNEXION ===")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Message d'erreur: {str(e)}")
            logger.error(f"URL tentée: {url_destination}")
            logger.error(f"Destination: {destination_name}")
            logger.error(f"Alerte ID: {alerte.id}")
            logger.error(f"=== FIN ERREUR ===")
            
            return JsonResponse({
                'success': False,
                'message': f'Erreur de connexion vers le {destination_name}: {str(e)}',
                'alerte_id': alerte.id,
                'titre': alerte.titre,
                'niveau': alerte.niveau,
                'destination': destination_name,
                'sent': False,
                'error_type': type(e).__name__,
                'url_attempted': url_destination
            }, status=500)
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'alerte: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def lister_alertes_actives(request):
    """
    Liste les alertes actives
    GET /api/alertes/actives/
    """
    try:
        alertes = AlerteEnrichie.objects.filter(
            est_active=True,
            est_resolue=False
        ).order_by('-date_creation')
        
        alertes_data = []
        for alerte in alertes:
            alertes_data.append({
                'id': alerte.id,
                'titre': alerte.titre,
                'description': alerte.description,
                'niveau': alerte.niveau,
                'type': alerte.type,
                'zone': alerte.zone.nom,
                'date_creation': alerte.date_creation.isoformat(),
                'actions_requises': alerte.actions_requises
            })
        
        return JsonResponse({
            'success': True,
            'message': f'{len(alertes_data)} alertes actives trouvées',
            'alertes': alertes_data
        }, status=200)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des alertes: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=500)
