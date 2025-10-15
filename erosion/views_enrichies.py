"""
Nouvelles vues pour les fonctionnalités enrichies
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime
# from drf_spectacular.utils import extend_schema, extend_schema_view  # Désactivé temporairement

from .models import (
    CleAPI, DonneesCartographiques, DonneesEnvironnementales, 
    AnalyseErosion, LogAPICall, Zone
)
from .serializers import (
    CleAPISerializer, DonneesCartographiquesSerializer, DonneesEnvironnementalesSerializer,
    AnalyseErosionSerializer, LogAPICallSerializer, DonneesConsolideesSerializer,
    PredictionEnrichieSerializer
)


class CleAPIViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des clés API"""
    queryset = CleAPI.objects.all()
    serializer_class = CleAPISerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['service', 'actif']
    search_fields = ['service', 'url_base']
    ordering_fields = ['service', 'date_creation']
    ordering = ['service']


class DonneesCartographiquesViewSet(viewsets.ModelViewSet):
    """ViewSet pour les données cartographiques"""
    schema = None  # Désactiver complètement la génération de schéma
    queryset = DonneesCartographiques.objects.all()
    serializer_class = DonneesCartographiquesSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'type_donnees', 'source', 'qualite_donnees']
    search_fields = ['zone__nom', 'source']
    ordering_fields = ['date_acquisition', 'date_traitement']
    ordering = ['-date_acquisition']


class DonneesEnvironnementalesViewSet(viewsets.ModelViewSet):
    """ViewSet pour les données environnementales consolidées"""
    queryset = DonneesEnvironnementales.objects.all()
    serializer_class = DonneesEnvironnementalesSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'periode_debut', 'periode_fin']
    search_fields = ['zone__nom']
    ordering_fields = ['date_collecte', 'periode_debut', 'periode_fin']
    ordering = ['-date_collecte']
    
    @action(detail=False, methods=['post'])
    def collecter_donnees(self, request):
        """Collecte les données environnementales pour une zone"""
        from .services import DataConsolidationService
        
        zone_id = request.data.get('zone_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not all([zone_id, start_date, end_date]):
            return Response(
                {'erreur': 'zone_id, start_date et end_date sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            zone = Zone.objects.get(id=zone_id)
            consolidation_service = DataConsolidationService()
            
            # Collecter toutes les données
            consolidated_data = consolidation_service.collect_all_data(zone, start_date, end_date)
            
            # Sauvegarder les données
            donnees_env = consolidation_service.save_consolidated_data(zone, consolidated_data)
            
            serializer = DonneesEnvironnementalesSerializer(donnees_env)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Zone.DoesNotExist:
            return Response(
                {'erreur': 'Zone non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'erreur': f'Erreur lors de la collecte: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyseErosionViewSet(viewsets.ModelViewSet):
    """ViewSet pour les analyses d'érosion enrichies"""
    queryset = AnalyseErosion.objects.all()
    serializer_class = AnalyseErosionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'niveau_urgence', 'modele_utilise']
    search_fields = ['zone__nom', 'modele_utilise']
    ordering_fields = ['date_analyse', 'taux_erosion_predit', 'confiance_prediction']
    ordering = ['-date_analyse']
    
    @action(detail=False, methods=['post'])
    def analyser_zone(self, request):
        """Effectue une analyse d'érosion enrichie pour une zone"""
        zone_id = request.data.get('zone_id')
        horizon_jours = request.data.get('horizon_jours', 30)
        
        if not zone_id:
            return Response(
                {'erreur': 'zone_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            zone = Zone.objects.get(id=zone_id)
            
            # Récupérer les données environnementales les plus récentes
            donnees_env = DonneesEnvironnementales.objects.filter(zone=zone).order_by('-date_collecte').first()
            
            if not donnees_env:
                return Response(
                    {'erreur': 'Aucune donnée environnementale disponible pour cette zone'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Effectuer l'analyse d'érosion enrichie
            analyse = self._calculer_analyse_erosion(zone, donnees_env, horizon_jours)
            
            serializer = AnalyseErosionSerializer(analyse)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Zone.DoesNotExist:
            return Response(
                {'erreur': 'Zone non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'erreur': f'Erreur lors de l\'analyse: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculer_analyse_erosion(self, zone, donnees_env, horizon_jours):
        """Calcule une analyse d'érosion enrichie"""
        # Algorithme simplifié d'analyse d'érosion multi-facteurs
        
        # Facteurs météorologiques
        facteur_meteo = 0.0
        if donnees_env.vitesse_vent and donnees_env.vitesse_vent > 10:
            facteur_meteo += 0.3
        if donnees_env.precipitation_totale and donnees_env.precipitation_totale > 50:
            facteur_meteo += 0.2
        
        # Facteurs marins
        facteur_marin = 0.0
        if donnees_env.amplitude_maree and donnees_env.amplitude_maree > 3:
            facteur_marin += 0.4
        if donnees_env.vitesse_courant and donnees_env.vitesse_courant > 0.5:
            facteur_marin += 0.3
        
        # Facteurs topographiques
        facteur_topographique = 0.0
        if donnees_env.pente_moyenne and donnees_env.pente_moyenne > 5:
            facteur_topographique += 0.2
        if donnees_env.elevation_moyenne and donnees_env.elevation_moyenne < 5:
            facteur_topographique += 0.3
        
        # Calcul du taux d'érosion prédit
        taux_base = 0.1  # mètres/an de base
        taux_erosion_predit = taux_base + (facteur_meteo + facteur_marin + facteur_topographique) * 0.5
        
        # Calcul de la confiance
        confiance_prediction = 75.0  # Confiance de base
        if donnees_env.donnees_completes.get('erreurs'):
            confiance_prediction -= len(donnees_env.donnees_completes['erreurs']) * 5
        
        # Détermination du niveau d'urgence
        if taux_erosion_predit > 1.0:
            niveau_urgence = 'critique'
        elif taux_erosion_predit > 0.5:
            niveau_urgence = 'eleve'
        elif taux_erosion_predit > 0.2:
            niveau_urgence = 'modere'
        else:
            niveau_urgence = 'faible'
        
        # Génération des recommandations
        recommandations = []
        if facteur_meteo > 0.3:
            recommandations.append("Surveiller les conditions météorologiques extrêmes")
        if facteur_marin > 0.5:
            recommandations.append("Renforcer les protections contre les marées")
        if facteur_topographique > 0.3:
            recommandations.append("Considérer des mesures de stabilisation du terrain")
        
        # Création de l'analyse
        analyse = AnalyseErosion.objects.create(
            zone=zone,
            donnees_environnementales=donnees_env,
            horizon_prediction_jours=horizon_jours,
            taux_erosion_predit=taux_erosion_predit,
            confiance_prediction=max(0, min(100, confiance_prediction)),
            facteur_meteo=facteur_meteo,
            facteur_marin=facteur_marin,
            facteur_topographique=facteur_topographique,
            recommandations=recommandations,
            niveau_urgence=niveau_urgence,
            calculs_detaille={
                'taux_base': taux_base,
                'facteurs_appliques': {
                    'meteo': facteur_meteo,
                    'marin': facteur_marin,
                    'topographique': facteur_topographique
                },
                'algorithme_version': '1.0'
            }
        )
        
        return analyse


class LogAPICallViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les logs d'appels API (lecture seule)"""
    queryset = LogAPICall.objects.all()
    serializer_class = LogAPICallSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['service_api', 'statut_reponse', 'utilisateur']
    search_fields = ['service_api', 'endpoint_appele']
    ordering_fields = ['timestamp', 'temps_reponse_ms']
    ordering = ['-timestamp']


class PredictionEnrichieViewSet(viewsets.ViewSet):
    """ViewSet pour les prédictions enrichies"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Liste les prédictions enrichies disponibles"""
        return Response({
            "message": "Endpoint pour les prédictions enrichies",
            "actions_disponibles": [
                "POST /api/predictions-enrichies/generer-prediction/",
            ],
            "description": "Utilisez l'action 'generer-prediction' pour créer une prédiction enrichie"
        })
    
    @action(detail=False, methods=['post'])
    def generer_prediction(self, request):
        """Génère une prédiction enrichie pour une zone"""
        zone_id = request.data.get('zone_id')
        horizon_jours = request.data.get('horizon_jours', 30)
        
        if not zone_id:
            return Response(
                {'erreur': 'zone_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            zone = Zone.objects.get(id=zone_id)
            
            # Récupérer les données environnementales
            donnees_env = DonneesEnvironnementales.objects.filter(zone=zone).order_by('-date_collecte').first()
            
            if not donnees_env:
                return Response(
                    {'erreur': 'Aucune donnée environnementale disponible'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Effectuer l'analyse d'érosion
            analyse = AnalyseErosion.objects.filter(
                zone=zone,
                donnees_environnementales=donnees_env
            ).order_by('-date_analyse').first()
            
            if not analyse:
                # Créer une nouvelle analyse si nécessaire
                analyse_view = AnalyseErosionViewSet()
                analyse = analyse_view._calculer_analyse_erosion(zone, donnees_env, horizon_jours)
            
            # Construire la réponse enrichie
            prediction_enrichie = {
                'zone_id': zone.id,
                'zone_nom': zone.nom,
                'date_prediction': analyse.date_analyse,
                'horizon_jours': horizon_jours,
                'taux_erosion_predit': analyse.taux_erosion_predit,
                'confiance_prediction': analyse.confiance_prediction,
                'facteurs_influence': {
                    'meteo': analyse.facteur_meteo,
                    'marin': analyse.facteur_marin,
                    'topographique': analyse.facteur_topographique,
                    'substrat': analyse.facteur_substrat
                },
                'donnees_environnementales': DonneesEnvironnementalesSerializer(donnees_env).data,
                'analyses_detaillees': [analyse.calculs_detaille],
                'recommandations': analyse.recommandations,
                'niveau_urgence': analyse.niveau_urgence,
                'modele_ml': analyse.modele_ml.nom if analyse.modele_ml else 'N/A',
                'version_modele': '1.0',
                'date_calcul': analyse.date_analyse
            }
            
            serializer = PredictionEnrichieSerializer(prediction_enrichie)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Zone.DoesNotExist:
            return Response(
                {'erreur': 'Zone non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'erreur': f'Erreur lors de la génération: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
