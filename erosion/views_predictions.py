"""
Vues pour les prédictions ML d'érosion
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
import logging

# Documentation Swagger
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Zone, ModeleML, Prediction
from .serializers import (
    PredictionRequestSerializer, 
    PredictionMLSerializer, 
    ModeleMLSerializer
)
from .ml_services import MLPredictionService

logger = logging.getLogger(__name__)


@extend_schema(
    operation_id='predict_erosion',
    summary='Prédire l\'érosion d\'une zone',
    description='''
    Calcule une prédiction d'érosion pour une zone donnée en utilisant les modèles ML entraînés.
    
    Cette fonction utilise les données des capteurs Arduino, l'historique d'érosion et les 
    données environnementales pour générer une prédiction avec intervalle de confiance.
    
    **Permissions requises:** 
    - Admin: Accès complet
    - Scientifique: Accès à toutes les zones
    - Technicien: Accès aux zones de son organisation
    - Observateur: Accès refusé
    ''',
    tags=['Prédictions ML'],
    request=PredictionRequestSerializer,
    responses={
        201: PredictionMLSerializer,
        400: {
            'description': 'Données de requête invalides',
            'examples': {
                'zone_not_found': {
                    'summary': 'Zone non trouvée',
                    'value': {'error': 'Zone 999 non trouvée'}
                },
                'invalid_features': {
                    'summary': 'Features invalides',
                    'value': {'error': 'Données de requête invalides', 'details': {'features': {'temperature_supplementaire': ['La feature \'temperature_supplementaire\' doit être numérique.']}}}
                }
            }
        },
        403: {
            'description': 'Permissions insuffisantes',
            'examples': {
                'insufficient_permissions': {
                    'summary': 'Permissions insuffisantes',
                    'value': {'error': 'Permissions insuffisantes pour cette zone'}
                }
            }
        },
        500: {
            'description': 'Erreur interne du serveur',
            'examples': {
                'server_error': {
                    'summary': 'Erreur serveur',
                    'value': {'error': 'Erreur interne du serveur', 'details': 'Aucun modèle ML actif trouvé'}
                }
            }
        }
    },
    examples=[
        OpenApiExample(
            'Prédiction basique',
            summary='Prédiction simple pour 30 jours',
            description='Exemple de prédiction basique pour une zone',
            value={
                'zone_id': 1,
                'horizon_jours': 30,
                'commentaires': 'Prédiction pour analyse saisonnière'
            }
        ),
        OpenApiExample(
            'Prédiction avec features',
            summary='Prédiction avec données supplémentaires',
            description='Exemple avec des features environnementales supplémentaires',
            value={
                'zone_id': 1,
                'horizon_jours': 90,
                'features': {
                    'temperature_supplementaire': 25.5,
                    'vent_supplementaire': 15.2,
                    'pression_supplementaire': 1013.25
                },
                'commentaires': 'Prédiction avec données météo supplémentaires'
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_erosion(request):
    """
    Endpoint pour prédire l'érosion d'une zone
    
    POST /api/predict/
    
    Body:
    {
        "zone_id": 1,
        "horizon_jours": 30,
        "features": {
            "temperature_supplementaire": 25.5,
            "vent_supplementaire": 15.2
        },
        "commentaires": "Prédiction pour analyse saisonnière"
    }
    
    Returns:
    {
        "id": 123,
        "zone": 1,
        "zone_nom": "Côte Atlantique",
        "modele_ml": 5,
        "modele_nom": "Random Forest Erosion",
        "modele_version": "1.20241201",
        "modele_type": "random_forest",
        "date_prediction": "2024-12-01T10:30:00Z",
        "horizon_jours": 30,
        "taux_erosion_pred_m_an": 0.15,
        "taux_erosion_min_m_an": 0.12,
        "taux_erosion_max_m_an": 0.18,
        "intervalle_confiance": {
            "min": 0.12,
            "max": 0.18,
            "largeur": 0.06
        },
        "confiance_pourcentage": 85.5,
        "score_confiance": 0.855,
        "features_entree": {...},
        "parametres_prediction": {...},
        "commentaires": "Prédiction générée par Random Forest Erosion v1.20241201"
    }
    """
    logger.info(f"Requête de prédiction reçue de l'utilisateur {request.user.username}")
    
    try:
        # Valider les données d'entrée
        serializer = PredictionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Données de prédiction invalides: {serializer.errors}")
            return Response(
                {
                    'error': 'Données de requête invalides',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        zone_id = validated_data['zone_id']
        horizon_jours = validated_data.get('horizon_jours', 30)
        features = validated_data.get('features', {})
        commentaires = validated_data.get('commentaires', '')
        
        # Vérifier que la zone existe
        try:
            zone = Zone.objects.get(id=zone_id)
        except Zone.DoesNotExist:
            logger.warning(f"Zone {zone_id} non trouvée")
            return Response(
                {'error': f'Zone {zone_id} non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérifier les permissions utilisateur
        if not _check_prediction_permissions(request.user, zone):
            logger.warning(f"Utilisateur {request.user.username} n'a pas les permissions pour la zone {zone_id}")
            return Response(
                {'error': 'Permissions insuffisantes pour cette zone'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Effectuer la prédiction avec transaction atomique
        with transaction.atomic():
            ml_service = MLPredictionService()
            prediction = ml_service.predire_erosion(
                zone_id=zone_id,
                features=features,
                horizon_jours=horizon_jours
            )
            
            # Ajouter les commentaires utilisateur si fournis
            if commentaires:
                prediction.commentaires = f"{prediction.commentaires}\n\nCommentaires utilisateur: {commentaires}"
                prediction.save()
        
        # Sérialiser et retourner la réponse
        response_serializer = PredictionMLSerializer(prediction)
        
        logger.info(f"Prédiction créée avec succès: ID {prediction.id} pour la zone {zone.nom}")
        
        return Response(
            {
                'success': True,
                'message': f'Prédiction générée avec succès pour la zone {zone.nom}',
                'prediction': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
        
    except ValueError as e:
        logger.error(f"Erreur de validation lors de la prédiction: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la prédiction: {e}")
        return Response(
            {
                'error': 'Erreur interne du serveur',
                'details': str(e) if logger.level <= logging.DEBUG else 'Erreur technique'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='get_active_model',
    summary='Récupérer le modèle ML actif',
    description='''
    Retourne les informations du modèle ML actuellement actif pour les prédictions.
    
    Le modèle actif est celui utilisé par défaut pour toutes les nouvelles prédictions.
    Un seul modèle peut être actif à la fois.
    ''',
    tags=['Modèles ML'],
    responses={
        200: ModeleMLSerializer,
        404: {
            'description': 'Aucun modèle actif',
            'examples': {
                'no_active_model': {
                    'summary': 'Aucun modèle actif',
                    'value': {'error': 'Aucun modèle ML actif trouvé'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_model(request):
    """
    Récupère le modèle ML actif
    
    GET /api/models/active/
    
    Returns:
    {
        "id": 5,
        "nom": "Random Forest Erosion",
        "version": "1.20241201",
        "type_modele": "random_forest",
        "statut": "actif",
        "precision_score": 0.85,
        "features_utilisees": [...],
        "date_creation": "2024-12-01T10:00:00Z",
        "date_derniere_utilisation": "2024-12-01T10:30:00Z",
        "nombre_predictions": 15,
        "commentaires": "..."
    }
    """
    try:
        active_model = ModeleML.objects.filter(statut='actif').first()
        
        if not active_model:
            return Response(
                {'error': 'Aucun modèle ML actif trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ModeleMLSerializer(active_model)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du modèle actif: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération du modèle'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='get_model_performance',
    summary='Récupérer les performances d\'un modèle ML',
    description='''
    Retourne les performances détaillées d'un modèle ML spécifique, incluant :
    - Score de précision (R²)
    - Erreur quadratique moyenne (MSE)
    - Nombre de prédictions effectuées
    - Prédictions récentes (dernières 10)
    ''',
    tags=['Modèles ML'],
    parameters=[
        OpenApiParameter(
            name='model_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='ID du modèle ML'
        )
    ],
    responses={
        200: {
            'description': 'Performances du modèle',
            'examples': {
                'model_performance': {
                    'summary': 'Performances d\'un modèle',
                    'value': {
                        'model': {
                            'id': 5,
                            'nom': 'Random Forest Erosion',
                            'version': '1.20241201',
                            'type_modele': 'random_forest',
                            'precision_score': 0.85,
                            'nombre_predictions': 15
                        },
                        'performance': {
                            'precision_score': 0.85,
                            'mse': 0.02,
                            'r2_score': 0.85,
                            'nombre_predictions': 15,
                            'derniere_utilisation': '2024-12-01T10:30:00Z',
                            'predictions_recentes': []
                        }
                    }
                }
            }
        },
        404: {
            'description': 'Modèle non trouvé',
            'examples': {
                'model_not_found': {
                    'summary': 'Modèle non trouvé',
                    'value': {'error': 'Modèle 999 non trouvé'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_model_performance(request, model_id):
    """
    Récupère les performances d'un modèle ML
    
    GET /api/models/{model_id}/performance/
    
    Returns:
    {
        "model": {...},
        "performance": {
            "precision_score": 0.85,
            "mse": 0.02,
            "nombre_predictions": 15,
            "derniere_utilisation": "2024-12-01T10:30:00Z",
            "predictions_recentes": [...]
        }
    }
    """
    try:
        model = ModeleML.objects.get(id=model_id)
        
        # Récupérer les prédictions récentes (dernières 10)
        recent_predictions = Prediction.objects.filter(
            modele_ml=model
        ).order_by('-date_prediction')[:10]
        
        performance_data = {
            'precision_score': model.precision_score,
            'mse': model.parametres_entrainement.get('mse'),
            'r2_score': model.parametres_entrainement.get('r2_score'),
            'nombre_predictions': model.nombre_predictions,
            'derniere_utilisation': model.date_derniere_utilisation,
            'predictions_recentes': PredictionMLSerializer(recent_predictions, many=True).data
        }
        
        model_serializer = ModeleMLSerializer(model)
        
        return Response({
            'model': model_serializer.data,
            'performance': performance_data
        })
        
    except ModeleML.DoesNotExist:
        return Response(
            {'error': f'Modèle {model_id} non trouvé'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des performances: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des performances'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='get_zone_predictions',
    summary='Récupérer les prédictions d\'une zone',
    description='''
    Retourne les prédictions ML pour une zone spécifique avec possibilité de filtrage.
    
    **Paramètres de requête:**
    - `limit`: Nombre de prédictions à retourner (défaut: 10)
    - `horizon_jours`: Filtrer par horizon de prédiction
    
    **Permissions:** Même logique que pour les prédictions
    ''',
    tags=['Prédictions ML'],
    parameters=[
        OpenApiParameter(
            name='zone_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='ID de la zone'
        ),
        OpenApiParameter(
            name='limit',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Nombre de prédictions à retourner (défaut: 10)',
            default=10
        ),
        OpenApiParameter(
            name='horizon_jours',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Filtrer par horizon de prédiction en jours'
        )
    ],
    responses={
        200: {
            'description': 'Prédictions de la zone',
            'examples': {
                'zone_predictions': {
                    'summary': 'Prédictions d\'une zone',
                    'value': {
                        'zone': {
                            'id': 1,
                            'nom': 'Côte Atlantique',
                            'niveau_risque': 'modere',
                            'superficie_km2': 150.5
                        },
                        'predictions': [
                            {
                                'id': 123,
                                'zone': 1,
                                'zone_nom': 'Côte Atlantique',
                                'modele_ml': 5,
                                'modele_nom': 'Random Forest Erosion',
                                'date_prediction': '2024-12-01T10:30:00Z',
                                'horizon_jours': 30,
                                'taux_erosion_pred_m_an': 0.15,
                                'confiance_pourcentage': 85.5
                            }
                        ],
                        'statistiques': {
                            'nombre_total': 25,
                            'derniere_prediction': '2024-12-01T10:30:00Z',
                            'taux_moyen': 0.15,
                            'confiance_moyenne': 82.5
                        }
                    }
                }
            }
        },
        403: {
            'description': 'Permissions insuffisantes',
            'examples': {
                'insufficient_permissions': {
                    'summary': 'Permissions insuffisantes',
                    'value': {'error': 'Permissions insuffisantes pour cette zone'}
                }
            }
        },
        404: {
            'description': 'Zone non trouvée',
            'examples': {
                'zone_not_found': {
                    'summary': 'Zone non trouvée',
                    'value': {'error': 'Zone 999 non trouvée'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_zone_predictions(request, zone_id):
    """
    Récupère les prédictions pour une zone
    
    GET /api/zones/{zone_id}/predictions/
    
    Query parameters:
    - limit: nombre de prédictions à retourner (défaut: 10)
    - horizon_jours: filtrer par horizon de prédiction
    
    Returns:
    {
        "zone": {...},
        "predictions": [...],
        "statistiques": {
            "nombre_total": 25,
            "derniere_prediction": "2024-12-01T10:30:00Z",
            "taux_moyen": 0.15,
            "confiance_moyenne": 82.5
        }
    }
    """
    try:
        zone = Zone.objects.get(id=zone_id)
        
        # Vérifier les permissions
        if not _check_prediction_permissions(request.user, zone):
            return Response(
                {'error': 'Permissions insuffisantes pour cette zone'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Paramètres de requête
        limit = int(request.query_params.get('limit', 10))
        horizon_jours = request.query_params.get('horizon_jours')
        
        # Construire la requête
        predictions_query = Prediction.objects.filter(zone=zone)
        
        if horizon_jours:
            predictions_query = predictions_query.filter(horizon_jours=horizon_jours)
        
        predictions = predictions_query.order_by('-date_prediction')[:limit]
        
        # Calculer les statistiques
        all_predictions = Prediction.objects.filter(zone=zone)
        stats = {
            'nombre_total': all_predictions.count(),
            'derniere_prediction': all_predictions.first().date_prediction if all_predictions.exists() else None,
            'taux_moyen': all_predictions.aggregate(avg='taux_erosion_pred_m_an')['avg'] or 0,
            'confiance_moyenne': all_predictions.aggregate(avg='confiance_pourcentage')['avg'] or 0
        }
        
        # Sérialiser les données
        zone_serializer = {
            'id': zone.id,
            'nom': zone.nom,
            'niveau_risque': zone.niveau_risque,
            'superficie_km2': zone.superficie_km2
        }
        
        predictions_serializer = PredictionMLSerializer(predictions, many=True)
        
        return Response({
            'zone': zone_serializer,
            'predictions': predictions_serializer.data,
            'statistiques': stats
        })
        
    except Zone.DoesNotExist:
        return Response(
            {'error': f'Zone {zone_id} non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des prédictions: {e}")
        return Response(
            {'error': 'Erreur lors de la récupération des prédictions'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _check_prediction_permissions(user, zone):
    """
    Vérifie si l'utilisateur a les permissions pour faire des prédictions sur cette zone
    
    Args:
        user: Utilisateur Django
        zone: Objet Zone
        
    Returns:
        bool: True si l'utilisateur a les permissions
    """
    # Les administrateurs ont accès à tout
    if user.role == 'admin':
        return True
    
    # Les scientifiques peuvent prédire sur toutes les zones
    if user.role == 'scientifique':
        return True
    
    # Les techniciens peuvent prédire sur les zones de leur organisation
    if user.role == 'technicien':
        # Pour l'instant, permettre l'accès à toutes les zones
        # TODO: Implémenter la logique d'organisation si nécessaire
        return True
    
    # Les observateurs ne peuvent pas faire de prédictions
    if user.role == 'observateur':
        return False
    
    return False
