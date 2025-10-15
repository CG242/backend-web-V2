from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
# from django.contrib.gis.geos import Point, Polygon  # Désactivé temporairement
from django.db.models import Avg, Min, Max, Count
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    Utilisateur, Zone, HistoriqueErosion, Capteur, Mesure, 
    Prediction, TendanceLongTerme, Alerte, EvenementClimatique, JournalAction,
    CleAPI, DonneesCartographiques, DonneesEnvironnementales, 
    AnalyseErosion, LogAPICall
)
from .serializers import (
    UtilisateurSerializer, ZoneSerializer, HistoriqueErosionSerializer,
    CapteurSerializer, MesureSerializer, PredictionSerializer,
    TendanceLongTermeSerializer, AlerteSerializer, EvenementClimatiqueSerializer,
    JournalActionSerializer, StatistiquesZoneSerializer, MesureStatistiqueSerializer,
    CleAPISerializer, DonneesCartographiquesSerializer, DonneesEnvironnementalesSerializer,
    AnalyseErosionSerializer, LogAPICallSerializer, DonneesConsolideesSerializer,
    PredictionEnrichieSerializer, ZoneDocSerializer, CapteurDocSerializer
)
from .filters import (
    ZoneFilter, CapteurFilter, MesureFilter, PredictionFilter,
    AlerteFilter, HistoriqueErosionFilter, TendanceLongTermeFilter, EvenementClimatiqueFilter
)
# from drf_spectacular.utils import extend_schema, extend_schema_view  # Désactivé temporairement


class UtilisateurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des utilisateurs"""
    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'organisation']
    ordering_fields = ['username', 'date_joined', 'last_login']
    ordering = ['username']


class ZoneViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des zones géographiques"""
    schema = None  # Désactiver complètement la génération de schéma
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ZoneFilter
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'superficie_km2', 'date_creation']
    ordering = ['nom']
    
    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Récupère les statistiques d'une zone"""
        zone = self.get_object()
        
        # Statistiques des capteurs
        capteurs = zone.capteurs.all()
        nombre_capteurs = capteurs.count()
        
        # Statistiques des mesures
        mesures = Mesure.objects.filter(capteur__zone=zone)
        nombre_mesures_total = mesures.count()
        derniere_mesure = mesures.first().timestamp if mesures.exists() else None
        
        # Statistiques d'érosion
        historique = zone.historique_erosion.all()
        taux_erosion_moyen = historique.aggregate(Avg('taux_erosion_m_an'))['taux_erosion_m_an__avg'] or 0
        
        # Alertes actives
        alertes_actives = zone.alertes.filter(est_resolue=False).count()
        
        data = {
            'zone_id': zone.id,
            'zone_nom': zone.nom,
            'nombre_capteurs': nombre_capteurs,
            'nombre_mesures_total': nombre_mesures_total,
            'derniere_mesure': derniere_mesure,
            'taux_erosion_moyen': taux_erosion_moyen,
            'nombre_alertes_actives': alertes_actives,
            'niveau_risque': zone.niveau_risque
        }
        
        serializer = StatistiquesZoneSerializer(data)
        return Response(serializer.data)


class HistoriqueErosionViewSet(viewsets.ModelViewSet):
    """ViewSet pour l'historique des mesures d'érosion"""
    queryset = HistoriqueErosion.objects.all()
    serializer_class = HistoriqueErosionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'methode_mesure', 'utilisateur']
    search_fields = ['commentaires']
    ordering_fields = ['date_mesure', 'taux_erosion_m_an']
    ordering = ['-date_mesure']


class CapteurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des capteurs"""
    schema = None  # Désactiver complètement la génération de schéma
    queryset = Capteur.objects.all()
    serializer_class = CapteurSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CapteurFilter
    search_fields = ['nom', 'commentaires']
    ordering_fields = ['nom', 'date_installation']
    ordering = ['nom']
    
    @action(detail=True, methods=['get'])
    def mesures_recentes(self, request, pk=None):
        """Récupère les mesures récentes d'un capteur"""
        capteur = self.get_object()
        limite = request.query_params.get('limite', 100)
        
        mesures = capteur.mesures.all()[:int(limite)]
        serializer = MesureSerializer(mesures, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistiques_mesures(self, request, pk=None):
        """Récupère les statistiques des mesures d'un capteur"""
        capteur = self.get_object()
        
        # Période par défaut : 30 derniers jours
        periode_jours = int(request.query_params.get('periode_jours', 30))
        date_debut = timezone.now() - timedelta(days=periode_jours)
        
        mesures = capteur.mesures.filter(timestamp__gte=date_debut)
        
        if mesures.exists():
            stats = mesures.aggregate(
                moyenne=Avg('valeur'),
                minimum=Min('valeur'),
                maximum=Max('valeur'),
                nombre=Count('valeur')
            )
            
            data = {
                'capteur_id': capteur.id,
                'capteur_nom': capteur.nom,
                'type_capteur': capteur.type,
                'valeur_moyenne': stats['moyenne'],
                'valeur_min': stats['minimum'],
                'valeur_max': stats['maximum'],
                'nombre_mesures': stats['nombre'],
                'periode_debut': date_debut,
                'periode_fin': timezone.now()
            }
            
            serializer = MesureStatistiqueSerializer(data)
            return Response(serializer.data)
        
        return Response({'message': 'Aucune mesure trouvée pour cette période'}, 
                       status=status.HTTP_404_NOT_FOUND)


class MesureViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des mesures"""
    queryset = Mesure.objects.all()
    serializer_class = MesureSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MesureFilter
    search_fields = ['commentaires']
    ordering_fields = ['timestamp', 'valeur']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Filtre les mesures selon les paramètres de requête"""
        queryset = super().get_queryset()
        
        # Filtre par zone
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(capteur__zone_id=zone_id)
        
        # Filtre par type de capteur
        type_capteur = self.request.query_params.get('type_capteur')
        if type_capteur:
            queryset = queryset.filter(capteur__type=type_capteur)
        
        # Filtre par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(timestamp__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(timestamp__lte=date_fin)
        
        return queryset


class PredictionViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des prédictions"""
    queryset = Prediction.objects.all()
    serializer_class = PredictionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'modele_ml']
    search_fields = ['commentaires']
    ordering_fields = ['date_prediction', 'horizon_jours', 'confiance_pourcentage']
    ordering = ['-date_prediction']


class TendanceLongTermeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les tendances à long terme"""
    queryset = TendanceLongTerme.objects.all()
    serializer_class = TendanceLongTermeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'tendance']
    ordering_fields = ['date_analyse', 'taux_erosion_moyen_m_an']
    ordering = ['-date_analyse']


class AlerteViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des alertes"""
    queryset = Alerte.objects.all()
    serializer_class = AlerteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['zone', 'type', 'niveau', 'est_resolue']
    search_fields = ['titre', 'description']
    ordering_fields = ['date_creation', 'niveau']
    ordering = ['-date_creation']
    
    @action(detail=True, methods=['post'])
    def resoudre(self, request, pk=None):
        """Marque une alerte comme résolue"""
        alerte = self.get_object()
        alerte.est_resolue = True
        alerte.date_resolution = timezone.now()
        alerte.utilisateur_resolution = request.user
        alerte.save()
        
        serializer = self.get_serializer(alerte)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def actives(self, request):
        """Récupère toutes les alertes actives"""
        alertes_actives = self.get_queryset().filter(est_resolue=False)
        serializer = self.get_serializer(alertes_actives, many=True)
        return Response(serializer.data)


class EvenementClimatiqueViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des événements climatiques"""
    queryset = EvenementClimatique.objects.all()
    serializer_class = EvenementClimatiqueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'intensite']
    search_fields = ['nom', 'description']
    ordering_fields = ['date_debut', 'intensite']
    ordering = ['-date_debut']


class JournalActionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour le journal des actions"""
    queryset = JournalAction.objects.all()
    serializer_class = JournalActionSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['utilisateur', 'action', 'objet_type']
    search_fields = ['description']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Filtre le journal selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtre par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(timestamp__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(timestamp__lte=date_fin)
        
        return queryset