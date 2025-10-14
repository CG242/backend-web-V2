"""
Views pour la gestion des événements externes et la fusion de données
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from datetime import datetime, timedelta
import logging

from .models import (
    EvenementExterne, FusionDonnees, PredictionEnrichie, AlerteEnrichie, 
    ArchiveDonnees, Zone, MesureArduino
)
from .serializers import (
    EvenementExterneSerializer, EvenementExterneReceptionSerializer,
    FusionDonneesSerializer, PredictionEnrichieSerializer, 
    AlerteEnrichieSerializer, ArchiveDonneesSerializer,
    AnalyseFusionSerializer, StatistiquesEvenementsSerializer, 
    RapportFusionSerializer
)
from .services.analyse_fusion_service import AnalyseFusionService

logger = logging.getLogger(__name__)


class EvenementExterneViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des événements externes"""
    
    queryset = EvenementExterne.objects.all()
    serializer_class = EvenementExterneSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['type_evenement', 'zone', 'source', 'is_simulation', 'is_valide', 'is_traite']
    search_fields = ['description', 'source', 'source_id']
    ordering_fields = ['date_evenement', 'date_reception', 'intensite']
    ordering = ['-date_evenement']
    
    def get_queryset(self):
        """Filtre les événements selon les permissions"""
        queryset = super().get_queryset()
        
        # Filtre par zone si spécifié
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        # Filtre par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(date_evenement__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_evenement__lte=date_fin)
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='recevoir-evenement')
    def recevoir_evenement(self, request):
        """
        Endpoint pour recevoir un événement externe via API
        """
        serializer = EvenementExterneReceptionSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Créer l'événement
                evenement = serializer.save()
                
                # Marquer comme traité pour déclencher l'analyse
                evenement.is_traite = True
                evenement.save()
                
                # Déclencher l'analyse de fusion en arrière-plan
                from .tasks import analyser_fusion_evenement
                analyser_fusion_evenement.delay(evenement.id)
                
                logger.info(f"Événement externe reçu: {evenement.type_evenement} - {evenement.intensite}%")
                
                return Response({
                    'success': True,
                    'message': 'Événement reçu et en cours de traitement',
                    'evenement_id': evenement.id,
                    'status': 'en_analyse'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Erreur lors de la création de l'événement: {e}")
                return Response({
                    'success': False,
                    'message': f'Erreur lors de la création: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'message': 'Données invalides',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='recevoir-evenements-batch')
    def recevoir_evenements_batch(self, request):
        """
        Endpoint pour recevoir plusieurs événements en lot
        """
        evenements_data = request.data.get('evenements', [])
        
        if not evenements_data:
            return Response({
                'success': False,
                'message': 'Aucun événement fourni'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        evenements_crees = []
        erreurs = []
        
        for i, evenement_data in enumerate(evenements_data):
            serializer = EvenementExterneReceptionSerializer(data=evenement_data)
            
            if serializer.is_valid():
                try:
                    evenement = serializer.save()
                    evenement.is_traite = True
                    evenement.save()
                    evenements_crees.append(evenement.id)
                    
                    # Déclencher l'analyse pour chaque événement
                    from .tasks import analyser_fusion_evenement
                    analyser_fusion_evenement.delay(evenement.id)
                    
                except Exception as e:
                    erreurs.append(f"Événement {i+1}: {str(e)}")
            else:
                erreurs.append(f"Événement {i+1}: {serializer.errors}")
        
        logger.info(f"Batch d'événements traité: {len(evenements_crees)} créés, {len(erreurs)} erreurs")
        
        return Response({
            'success': len(erreurs) == 0,
            'message': f'{len(evenements_crees)} événements créés',
            'evenements_crees': evenements_crees,
            'erreurs': erreurs
        }, status=status.HTTP_201_CREATED if evenements_crees else status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='marquer-traite')
    def marquer_traite(self, request, pk=None):
        """
        Marquer un événement comme traité
        """
        evenement = self.get_object()
        evenement.is_traite = True
        evenement.save()
        
        # Déclencher l'analyse de fusion
        from .tasks import analyser_fusion_evenement
        analyser_fusion_evenement.delay(evenement.id)
        
        return Response({
            'success': True,
            'message': 'Événement marqué comme traité et analyse déclenchée'
        })
    
    @action(detail=False, methods=['get'], url_path='statistiques')
    def statistiques(self, request):
        """
        Statistiques des événements externes
        """
        zone_id = request.query_params.get('zone_id')
        periode_jours = int(request.query_params.get('periode_jours', 30))
        
        # Filtrer par zone et période
        queryset = self.get_queryset()
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        date_limite = timezone.now() - timedelta(days=periode_jours)
        queryset = queryset.filter(date_evenement__gte=date_limite)
        
        # Calculer les statistiques
        stats = {
            'zone_id': zone_id,
            'zone_nom': queryset.first().zone.nom if queryset.exists() and zone_id else 'Toutes zones',
            'periode_debut': date_limite,
            'periode_fin': timezone.now(),
            'nombre_evenements_total': queryset.count(),
            'nombre_evenements_par_type': dict(queryset.values_list('type_evenement').annotate(count=Count('id'))),
            'nombre_evenements_par_intensite': {
                'faible': queryset.filter(intensite__lte=25).count(),
                'moderee': queryset.filter(intensite__gt=25, intensite__lte=50).count(),
                'forte': queryset.filter(intensite__gt=50, intensite__lte=75).count(),
                'extreme': queryset.filter(intensite__gt=75).count(),
            },
            'nombre_evenements_24h': queryset.filter(date_evenement__gte=timezone.now() - timedelta(hours=24)).count(),
            'nombre_evenements_7j': queryset.filter(date_evenement__gte=timezone.now() - timedelta(days=7)).count(),
            'nombre_evenements_30j': queryset.filter(date_evenement__gte=timezone.now() - timedelta(days=30)).count(),
            'intensite_moyenne': queryset.aggregate(avg=Avg('intensite'))['avg'] or 0,
            'intensite_max': queryset.aggregate(max=Max('intensite'))['max'] or 0,
            'intensite_min': queryset.aggregate(min=Min('intensite'))['min'] or 0,
            'sources_uniques': list(queryset.values_list('source', flat=True).distinct()),
            'nombre_evenements_par_source': dict(queryset.values_list('source').annotate(count=Count('id'))),
            'nombre_evenements_traites': queryset.filter(is_traite=True).count(),
            'nombre_evenements_non_traites': queryset.filter(is_traite=False).count(),
            'nombre_evenements_simulation': queryset.filter(is_simulation=True).count(),
        }
        
        serializer = StatistiquesEvenementsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='evenements-recents')
    def evenements_recents(self, request):
        """
        Récupérer les événements récents (dernières 24h)
        """
        date_limite = timezone.now() - timedelta(hours=24)
        evenements = self.get_queryset().filter(date_evenement__gte=date_limite)
        
        serializer = self.get_serializer(evenements, many=True)
        return Response(serializer.data)


class FusionDonneesViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consulter les fusions de données"""
    
    queryset = FusionDonnees.objects.all()
    serializer_class = FusionDonneesSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['zone', 'statut', 'evenement_externe']
    ordering_fields = ['date_creation', 'score_erosion']
    ordering = ['-date_creation']
    
    @action(detail=False, methods=['post'], url_path='analyser-zone')
    def analyser_zone(self, request):
        """
        Analyser une zone spécifique pour créer une fusion de données
        """
        zone_id = request.data.get('zone_id')
        periode_jours = request.data.get('periode_jours', 7)
        
        if not zone_id:
            return Response({
                'success': False,
                'message': 'zone_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            zone = Zone.objects.get(id=zone_id)
            
            # Déclencher l'analyse en arrière-plan
            from .tasks import analyser_fusion_zone
            task = analyser_fusion_zone.delay(zone_id, periode_jours)
            
            return Response({
                'success': True,
                'message': f'Analyse de la zone {zone.nom} démarrée',
                'task_id': task.id,
                'zone_id': zone_id,
                'periode_jours': periode_jours
            })
            
        except Zone.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Zone introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'], url_path='rapport-fusion')
    def rapport_fusion(self, request):
        """
        Générer un rapport de fusion des données
        """
        periode_jours = int(request.query_params.get('periode_jours', 30))
        date_limite = timezone.now() - timedelta(days=periode_jours)
        
        # Statistiques des fusions
        fusions = FusionDonnees.objects.filter(date_creation__gte=date_limite)
        
        # Statistiques des événements et mesures utilisés
        evenements = EvenementExterne.objects.filter(date_evenement__gte=date_limite)
        mesures = MesureArduino.objects.filter(timestamp__gte=date_limite)
        
        # Prédictions générées
        predictions = PredictionEnrichie.objects.filter(date_prediction__gte=date_limite)
        
        # Alertes générées
        alertes = AlerteEnrichie.objects.filter(date_creation__gte=date_limite)
        
        rapport = {
            'periode_debut': date_limite,
            'periode_fin': timezone.now(),
            'zones_analysees': list(Zone.objects.values('id', 'nom')),
            'nombre_fusions_total': fusions.count(),
            'nombre_fusions_terminees': fusions.filter(statut='terminee').count(),
            'nombre_fusions_en_cours': fusions.filter(statut='en_cours').count(),
            'nombre_fusions_erreur': fusions.filter(statut='erreur').count(),
            'nombre_evenements_externes_total': evenements.count(),
            'nombre_mesures_arduino_total': mesures.count(),
            'nombre_predictions_generes': predictions.count(),
            'nombre_predictions_erosion_positive': predictions.filter(erosion_predite=True).count(),
            'nombre_predictions_erosion_negative': predictions.filter(erosion_predite=False).count(),
            'nombre_alertes_generes': alertes.count(),
            'nombre_alertes_par_niveau': dict(alertes.values_list('niveau').annotate(count=Count('id'))),
            'pourcentage_donnees_valides': (evenements.filter(is_valide=True).count() / evenements.count() * 100) if evenements.count() > 0 else 0,
            'pourcentage_fusions_reussies': (fusions.filter(statut='terminee').count() / fusions.count() * 100) if fusions.count() > 0 else 0,
            'date_generation': timezone.now(),
            'duree_traitement_secondes': 0  # Sera calculé par la tâche
        }
        
        serializer = RapportFusionSerializer(rapport)
        return Response(serializer.data)


class PredictionEnrichieViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consulter les prédictions enrichies"""
    
    queryset = PredictionEnrichie.objects.all()
    serializer_class = PredictionEnrichieSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['zone', 'erosion_predite', 'niveau_erosion', 'niveau_confiance']
    ordering_fields = ['date_prediction', 'confiance_pourcentage']
    ordering = ['-date_prediction']
    
    @action(detail=False, methods=['get'], url_path='predictions-actives')
    def predictions_actives(self, request):
        """
        Récupérer les prédictions actives (dernières 7 jours)
        """
        date_limite = timezone.now() - timedelta(days=7)
        predictions = self.get_queryset().filter(date_prediction__gte=date_limite)
        
        serializer = self.get_serializer(predictions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='predictions-erosion')
    def predictions_erosion(self, request):
        """
        Récupérer uniquement les prédictions d'érosion positive
        """
        predictions = self.get_queryset().filter(erosion_predite=True)
        
        serializer = self.get_serializer(predictions, many=True)
        return Response(serializer.data)


class AlerteEnrichieViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des alertes enrichies"""
    
    queryset = AlerteEnrichie.objects.all()
    serializer_class = AlerteEnrichieSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['zone', 'type', 'niveau', 'est_active', 'est_resolue']
    ordering_fields = ['date_creation', 'niveau']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Filtre les alertes selon les permissions"""
        queryset = super().get_queryset()
        
        # Filtre par zone si spécifié
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        # Filtre par niveau de criticité
        niveau = self.request.query_params.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau=niveau)
        
        return queryset
    
    @action(detail=True, methods=['post'], url_path='resoudre')
    def resoudre(self, request, pk=None):
        """
        Résoudre une alerte
        """
        alerte = self.get_object()
        alerte.est_resolue = True
        alerte.est_active = False
        alerte.date_resolution = timezone.now()
        alerte.utilisateur_resolution = request.user
        alerte.save()
        
        return Response({
            'success': True,
            'message': 'Alerte résolue'
        })
    
    @action(detail=False, methods=['get'], url_path='alertes-actives')
    def alertes_actives(self, request):
        """
        Récupérer les alertes actives
        """
        alertes = self.get_queryset().filter(est_active=True, est_resolue=False)
        
        serializer = self.get_serializer(alertes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='alertes-critiques')
    def alertes_critiques(self, request):
        """
        Récupérer les alertes critiques et d'urgence
        """
        alertes = self.get_queryset().filter(
            est_active=True, 
            est_resolue=False,
            niveau__in=['critique', 'urgence']
        )
        
        serializer = self.get_serializer(alertes, many=True)
        return Response(serializer.data)


class ArchiveDonneesViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des archives de données"""
    
    queryset = ArchiveDonnees.objects.all()
    serializer_class = ArchiveDonneesSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['type_donnees', 'zone', 'est_disponible']
    ordering_fields = ['date_archivage', 'periode_debut']
    ordering = ['-date_archivage']
    
    @action(detail=False, methods=['post'], url_path='creer-archive')
    def creer_archive(self, request):
        """
        Créer une archive de données
        """
        type_donnees = request.data.get('type_donnees')
        zone_id = request.data.get('zone_id')
        periode_jours = int(request.data.get('periode_jours', 30))
        
        if not type_donnees or not zone_id:
            return Response({
                'success': False,
                'message': 'type_donnees et zone_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            zone = Zone.objects.get(id=zone_id)
            
            # Déclencher l'archivage en arrière-plan
            from .tasks import creer_archive_donnees
            task = creer_archive_donnees.delay(type_donnees, zone_id, periode_jours)
            
            return Response({
                'success': True,
                'message': f'Archivage des {type_donnees} pour {zone.nom} démarré',
                'task_id': task.id,
                'type_donnees': type_donnees,
                'zone_id': zone_id,
                'periode_jours': periode_jours
            })
            
        except Zone.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Zone introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], url_path='purger-anciennes')
    def purger_anciennes(self, request):
        """
        Purger les anciennes archives
        """
        periode_jours = int(request.data.get('periode_jours', 365))
        
        # Déclencher la purge en arrière-plan
        from .tasks import purger_anciennes_archives
        task = purger_anciennes_archives.delay(periode_jours)
        
        return Response({
            'success': True,
            'message': f'Purge des archives de plus de {periode_jours} jours démarrée',
            'task_id': task.id,
            'periode_jours': periode_jours
        })
