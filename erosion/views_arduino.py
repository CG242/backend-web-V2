"""
Vues pour la gestion des capteurs Arduino Nano ESP32
- Réception des données des capteurs
- Gestion des capteurs Arduino
- Monitoring et statistiques
- Complétion des données manquantes
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Min, Max, Count, Q
from django.utils import timezone
from django.contrib.gis.geos import Point

from .models import (
    CapteurArduino, MesureArduino, DonneesManquantes, 
    LogCapteurArduino, Zone
)
from .serializers import (
    CapteurArduinoSerializer, CapteurArduinoDocSerializer,
    MesureArduinoSerializer, DonneesManquantesSerializer,
    LogCapteurArduinoSerializer, DonneesArduinoReceptionSerializer,
    StatistiquesCapteurArduinoSerializer, RapportEtatCapteursSerializer
)
from .services.analyse_fusion_service import AnalyseFusionService
from .ml_services import MLPredictionService

logger = logging.getLogger(__name__)


class CapteurArduinoViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des capteurs Arduino"""
    queryset = CapteurArduino.objects.all()
    serializer_class = CapteurArduinoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['zone', 'type_capteur', 'etat', 'actif']
    
    def get_queryset(self):
        """Filtre les capteurs selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtre par zone
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        # Filtre par état en ligne
        en_ligne = self.request.query_params.get('en_ligne')
        if en_ligne is not None:
            maintenant = timezone.now()
            timeout = timedelta(minutes=30)
            if en_ligne.lower() == 'true':
                queryset = queryset.filter(
                    date_derniere_communication__gte=maintenant - timeout
                )
            else:
                queryset = queryset.filter(
                    Q(date_derniere_communication__lt=maintenant - timeout) |
                    Q(date_derniere_communication__isnull=True)
                )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def mesures_recentes(self, request, pk=None):
        """Récupère les mesures récentes d'un capteur Arduino"""
        capteur = self.get_object()
        limite = int(request.query_params.get('limite', 100))
        heures = int(request.query_params.get('heures', 24))
        
        depuis = timezone.now() - timedelta(hours=heures)
        mesures = capteur.mesures_arduino.filter(
            timestamp__gte=depuis
        ).order_by('-timestamp')[:limite]
        
        serializer = MesureArduinoSerializer(mesures, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Récupère les statistiques détaillées d'un capteur"""
        capteur = self.get_object()
        periode_jours = int(request.query_params.get('periode_jours', 7))
        
        # Période d'analyse
        debut = timezone.now() - timedelta(days=periode_jours)
        
        # Mesures de la période
        mesures = capteur.mesures_arduino.filter(timestamp__gte=debut)
        
        # Statistiques de base
        stats = mesures.aggregate(
            total=Count('id'),
            valides=Count('id', filter=Q(est_valide=True)),
            reelles=Count('id', filter=Q(source_donnee='capteur_reel')),
            completees=Count('id', filter=Q(source_donnee__in=['interpolation', 'derniere_valeur']))
        )
        
        # Statistiques de valeurs (seulement pour les mesures valides)
        mesures_valides = mesures.filter(est_valide=True)
        if mesures_valides.exists():
            valeurs_stats = mesures_valides.aggregate(
                moyenne=Avg('valeur'),
                minimum=Min('valeur'),
                maximum=Max('valeur')
            )
        else:
            valeurs_stats = {'moyenne': 0, 'minimum': 0, 'maximum': 0}
        
        # Données manquantes
        donnees_manquantes = capteur.donnees_manquantes.filter(
            date_detection__gte=debut
        )
        
        data = {
            'capteur_id': capteur.id,
            'capteur_nom': capteur.nom,
            'type_capteur': capteur.type_capteur,
            'zone_nom': capteur.zone.nom,
            'etat': capteur.etat,
            'est_en_ligne': capteur.est_en_ligne,
            'derniere_communication': capteur.date_derniere_communication,
            'nombre_mesures_total': stats['total'],
            'nombre_mesures_24h': capteur.mesures_arduino.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'nombre_mesures_7j': capteur.mesures_arduino.filter(
                timestamp__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'nombre_mesures_30j': capteur.mesures_arduino.filter(
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'pourcentage_donnees_valides': (stats['valides'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'pourcentage_donnees_reelles': (stats['reelles'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'pourcentage_donnees_completees': (stats['completees'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'valeur_moyenne_24h': valeurs_stats['moyenne'],
            'valeur_min_24h': valeurs_stats['minimum'],
            'valeur_max_24h': valeurs_stats['maximum'],
            'tension_batterie': capteur.tension_batterie,
            'niveau_signal_wifi': capteur.niveau_signal_wifi,
            'version_firmware': capteur.version_firmware,
            'nombre_periodes_manquantes': donnees_manquantes.count(),
            'duree_totale_manquante_minutes': sum(
                dm.duree_manque_minutes for dm in donnees_manquantes
            )
        }
        
        serializer = StatistiquesCapteurArduinoSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def completer_donnees_manquantes(self, request, pk=None):
        """Déclenche la complétion des données manquantes pour un capteur (fonction simplifiée)"""
        capteur = self.get_object()
        periode_jours = int(request.data.get('periode_jours', 1))
        
        try:
            # Version simplifiée - juste retourner un message
            return Response({
                'message': f'Fonction de complétion simplifiée pour le capteur {capteur.nom}',
                'periode_jours': periode_jours,
                'note': 'Service de complétion automatique supprimé'
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la complétion des données: {str(e)}")
            return Response({
                'erreur': f'Erreur lors de la complétion: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Récupère les logs d'un capteur"""
        capteur = self.get_object()
        limite = int(request.query_params.get('limite', 50))
        niveau = request.query_params.get('niveau')
        
        logs = capteur.logs.all()
        if niveau:
            logs = logs.filter(niveau=niveau)
        
        logs = logs.order_by('-timestamp')[:limite]
        serializer = LogCapteurArduinoSerializer(logs, many=True)
        return Response(serializer.data)


class MesureArduinoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les mesures Arduino"""
    queryset = MesureArduino.objects.all()
    serializer_class = MesureArduinoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['capteur', 'qualite_donnee', 'source_donnee', 'est_valide']
    
    def get_queryset(self):
        """Filtre les mesures selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtre par zone
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(capteur__zone_id=zone_id)
        
        # Filtre par type de capteur
        type_capteur = self.request.query_params.get('type_capteur')
        if type_capteur:
            queryset = queryset.filter(capteur__type_capteur=type_capteur)
        
        # Filtre par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(timestamp__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(timestamp__lte=date_fin)
        
        # Filtre par source de données
        source_donnee = self.request.query_params.get('source_donnee')
        if source_donnee:
            queryset = queryset.filter(source_donnee=source_donnee)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistiques_globales(self, request):
        """Récupère les statistiques globales des mesures"""
        periode_jours = int(request.query_params.get('periode_jours', 7))
        debut = timezone.now() - timedelta(days=periode_jours)
        
        mesures = self.get_queryset().filter(timestamp__gte=debut)
        
        stats = mesures.aggregate(
            total=Count('id'),
            valides=Count('id', filter=Q(est_valide=True)),
            reelles=Count('id', filter=Q(source_donnee='capteur_reel')),
            completees=Count('id', filter=Q(source_donnee__in=['interpolation', 'derniere_valeur']))
        )
        
        # Répartition par qualité
        qualites = mesures.values('qualite_donnee').annotate(
            count=Count('id')
        ).order_by('qualite_donnee')
        
        # Répartition par source
        sources = mesures.values('source_donnee').annotate(
            count=Count('id')
        ).order_by('source_donnee')
        
        return Response({
            'periode_jours': periode_jours,
            'total_mesures': stats['total'],
            'mesures_valides': stats['valides'],
            'mesures_reelles': stats['reelles'],
            'mesures_completees': stats['completees'],
            'pourcentage_valides': (stats['valides'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'repartition_qualite': {q['qualite_donnee']: q['count'] for q in qualites},
            'repartition_source': {s['source_donnee']: s['count'] for s in sources}
        })


class DonneesManquantesViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les données manquantes"""
    queryset = DonneesManquantes.objects.all()
    serializer_class = DonneesManquantesSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['capteur', 'est_completee', 'type_completion']
    
    @action(detail=False, methods=['get'])
    def non_completees(self, request):
        """Récupère les données manquantes non complétées"""
        donnees_manquantes = self.get_queryset().filter(est_completee=False)
        serializer = self.get_serializer(donnees_manquantes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def completer(self, request, pk=None):
        """Complète une période de données manquantes spécifique"""
        donnees_manquantes = self.get_object()
        
        if donnees_manquantes.est_completee:
            return Response({
                'message': 'Cette période a déjà été complétée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            valeurs_completees = DataCompletionService.completer_donnees_manquantes(
                donnees_manquantes
            )
            
            return Response({
                'message': f'Complétion terminée: {valeurs_completees} valeurs créées',
                'valeurs_completees': valeurs_completees
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la complétion: {str(e)}")
            return Response({
                'erreur': f'Erreur lors de la complétion: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogCapteurArduinoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les logs des capteurs Arduino"""
    queryset = LogCapteurArduino.objects.all()
    serializer_class = LogCapteurArduinoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['capteur', 'type_evenement', 'niveau']
    
    def get_queryset(self):
        """Filtre les logs selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtre par zone
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(capteur__zone_id=zone_id)
        
        # Filtre par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(timestamp__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(timestamp__lte=date_fin)
        
        return queryset


# ============================================================================
# ENDPOINTS SPÉCIAUX POUR LA RÉCEPTION DES DONNÉES ARDUINO
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])  # Permettre l'accès sans authentification pour les capteurs
def recevoir_donnees_arduino(request):
    """
    Endpoint pour recevoir les données des capteurs Arduino (version simplifiée)
    NOTE: L'analyse et la prédiction déclenchées ci-dessous dérivent UNIQUEMENT
    des DERNIÈRES mesures disponibles sur la zone du capteur et des événements récents.
    Accessible sans authentification pour faciliter l'intégration
    """
    try:
        # Récupérer l'adresse IP source
        adresse_ip_source = request.META.get('REMOTE_ADDR')
        
        # Valider les données reçues
        serializer = DonneesArduinoReceptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        donnees_validees = serializer.validated_data
        
        # Version simplifiée - créer directement la mesure
        try:
            capteur = CapteurArduino.objects.get(adresse_mac=donnees_validees['mac_address'])
            
            mesure = MesureArduino.objects.create(
                capteur=capteur,
                valeur=donnees_validees['value'],
                unite=donnees_validees.get('unit', capteur.unite_mesure),
                timestamp=timezone.now(),
                qualite_donnee='bonne',
                source_donnee='capteur_reel',
                est_valide=True,
                donnees_brutes=json.dumps(donnees_validees, default=str)
            )
            
            # Mettre à jour la dernière communication du capteur
            capteur.date_derniere_communication = timezone.now()
            capteur.save()
            
            # Déclenchement synchrone: analyse + prédiction pour la zone du capteur
            try:
                if capteur.zone_id:
                    fusion_service = AnalyseFusionService()
                    fusion_service.analyser_zone(capteur.zone_id, periode_jours=1)
                    try:
                        ml_service = MLPredictionService()
                        ml_service.predire_erosion(zone_id=capteur.zone_id, features={}, horizon_jours=30)
                    except Exception as e:
                        logger.warning(f"Prediction ML non exécutée (Arduino): {e}")
            except Exception as e:
                logger.warning(f"Analyse synchrone non exécutée (Arduino): {e}")
            
            return Response({
                'success': True,
                'message': f'Données reçues et sauvegardées pour {capteur.nom}',
                'mesure_id': mesure.id,
                'timestamp_reception': str(timezone.now())
            }, status=status.HTTP_201_CREATED)
            
        except CapteurArduino.DoesNotExist:
            return Response({
                'success': False,
                'message': f'Capteur avec MAC {donnees_validees["mac_address"]} introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Erreur lors de la réception des données Arduino: {str(e)}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def recevoir_donnees_arduino_batch(request):
    """
    Endpoint pour recevoir plusieurs données Arduino en une seule requête
    """
    try:
        adresse_ip_source = request.META.get('REMOTE_ADDR')
        donnees_batch = request.data.get('data', [])
        
        if not isinstance(donnees_batch, list):
            return Response({
                'success': False,
                'message': 'Le champ "data" doit être une liste'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        resultats = []
        succes_total = 0
        erreurs_total = 0
        
        for donnees in donnees_batch:
            try:
                # Valider chaque donnée
                serializer = DonneesArduinoReceptionSerializer(data=donnees)
                if not serializer.is_valid():
                    resultats.append({
                        'success': False,
                        'errors': serializer.errors,
                        'data': donnees
                    })
                    erreurs_total += 1
                    continue
                
                # Version simplifiée - créer directement la mesure
                capteur = CapteurArduino.objects.get(adresse_mac=serializer.validated_data['mac_address'])
                
                mesure = MesureArduino.objects.create(
                    capteur=capteur,
                    valeur=serializer.validated_data['value'],
                    unite=serializer.validated_data.get('unit', capteur.unite_mesure),
                    timestamp=timezone.now(),
                    qualite_donnee='bonne',
                    source_donnee='capteur_reel',
                    est_valide=True,
                    donnees_brutes=json.dumps(serializer.validated_data, default=str)
                )
                
                capteur.date_derniere_communication = timezone.now()
                capteur.save()
                
                resultats.append({
                    'success': True,
                    'message': f'Données reçues pour {capteur.nom}',
                    'mesure_id': mesure.id
                })
                succes_total += 1
                    
            except Exception as e:
                resultats.append({
                    'success': False,
                    'message': f'Erreur de traitement: {str(e)}',
                    'data': donnees
                })
                erreurs_total += 1
        
        return Response({
            'success': True,
            'message': f'Traitement terminé: {succes_total} succès, {erreurs_total} erreurs',
            'total_traite': len(donnees_batch),
            'succes': succes_total,
            'erreurs': erreurs_total,
            'resultats': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la réception batch: {str(e)}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# ENDPOINTS DE MONITORING ET STATISTIQUES
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rapport_etat_capteurs(request):
    """Génère un rapport d'état des capteurs Arduino (version simplifiée)"""
    try:
        # Version simplifiée - générer le rapport directement
        capteurs = CapteurArduino.objects.filter(actif=True)
        
        # Statistiques de base
        total_capteurs = capteurs.count()
        capteurs_en_ligne = capteurs.filter(
            date_derniere_communication__gte=timezone.now() - timedelta(minutes=30)
        ).count()
        
        # Répartition par type
        types_capteurs = {}
        for type_code, type_nom in CapteurArduino.TYPE_CAPTEUR_CHOICES:
            count = capteurs.filter(type_capteur=type_code).count()
            types_capteurs[type_code] = {
                'nom': type_nom,
                'nombre': count
            }
        
        # Alertes
        maintenant = timezone.now()
        timeout = timedelta(minutes=30)
        
        alertes_batterie = LogCapteurArduino.objects.filter(
            type_evenement='batterie_faible',
            timestamp__gte=maintenant - timedelta(hours=24)
        ).count()
        
        alertes_wifi = LogCapteurArduino.objects.filter(
            type_evenement='erreur_wifi',
            timestamp__gte=maintenant - timedelta(hours=24)
        ).count()
        
        alertes_hors_ligne = capteurs.filter(
            Q(date_derniere_communication__lt=maintenant - timeout) |
            Q(date_derniere_communication__isnull=True)
        ).count()
        
        rapport = {
            'timestamp': maintenant.isoformat(),
            'capteurs': {
                'total': total_capteurs,
                'en_ligne': capteurs_en_ligne,
                'hors_ligne': alertes_hors_ligne,
                'pourcentage_en_ligne': (capteurs_en_ligne / total_capteurs * 100) if total_capteurs > 0 else 0
            },
            'types_capteurs': types_capteurs,
            'alertes_24h': {
                'batterie_faible': alertes_batterie,
                'erreur_wifi': alertes_wifi,
                'hors_ligne': alertes_hors_ligne
            },
            'statut_global': 'normal' if alertes_hors_ligne == 0 else 'attention'
        }
        
        serializer = RapportEtatCapteursSerializer(rapport)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la génération du rapport: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        rapport_complet = {
            **rapport,
            'types_capteurs': types_capteurs,
            'nombre_alertes_batterie': alertes_batterie,
            'nombre_alertes_wifi': alertes_wifi,
            'nombre_alertes_hors_ligne': alertes_hors_ligne,
            'pourcentage_en_ligne': (rapport['en_ligne'] / rapport['total_capteurs'] * 100) if rapport['total_capteurs'] > 0 else 0,
            'prochaine_verification': (maintenant + timedelta(minutes=5)).isoformat()
        }
        
        serializer = RapportEtatCapteursSerializer(rapport_complet)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la génération du rapport: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detecter_et_completer_donnees_manquantes(request):
    """Détecte et complète automatiquement toutes les données manquantes"""
    try:
        periode_jours = int(request.data.get('periode_jours', 1))
        capteur_id = request.data.get('capteur_id')  # Optionnel
        
        # Filtrer les capteurs
        if capteur_id:
            capteurs = CapteurArduino.objects.filter(id=capteur_id, actif=True)
        else:
            capteurs = CapteurArduino.objects.filter(actif=True)
        
        total_periodes = 0
        total_valeurs_completees = 0
        resultats = []
        
        for capteur in capteurs:
            try:
                # Détecter les données manquantes
                donnees_manquantes = DataCompletionService.detecter_donnees_manquantes(
                    capteur, periode_jours
                )
                
                capteur_completees = 0
                for dm in donnees_manquantes:
                    if not dm.est_completee:
                        dm.save()
                        completees = DataCompletionService.completer_donnees_manquantes(dm)
                        capteur_completees += completees
                        total_valeurs_completees += completees
                
                total_periodes += len(donnees_manquantes)
                
                resultats.append({
                    'capteur_id': capteur.id,
                    'capteur_nom': capteur.nom,
                    'periodes_detectees': len(donnees_manquantes),
                    'valeurs_completees': capteur_completees
                })
                
            except Exception as e:
                logger.error(f"Erreur pour le capteur {capteur.nom}: {str(e)}")
                resultats.append({
                    'capteur_id': capteur.id,
                    'capteur_nom': capteur.nom,
                    'erreur': str(e)
                })
        
        return Response({
            'message': f'Complétion terminée: {total_valeurs_completees} valeurs créées',
            'total_periodes_traitees': total_periodes,
            'total_valeurs_completees': total_valeurs_completees,
            'capteurs_traites': len(capteurs),
            'resultats': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la complétion globale: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la complétion: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# ENDPOINTS POUR LA DÉTECTION ET NOTIFICATION DES CAPTEURS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def etat_detection_capteurs(request):
    """Retourne l'état de détection de tous les capteurs"""
    try:
        # Capteurs connectés
        capteurs_connectes = CapteurDetectionService.detecter_capteurs_connectes()
        
        # Capteurs déconnectés
        capteurs_deconnectes = CapteurDetectionService.detecter_capteurs_deconnectes()
        
        # Statistiques
        total_capteurs = CapteurArduino.objects.filter(actif=True).count()
        
        data = {
            'total_capteurs': total_capteurs,
            'capteurs_connectes': {
                'nombre': capteurs_connectes.count(),
                'liste': [
                    {
                        'id': c.id,
                        'nom': c.nom,
                        'mac': c.adresse_mac,
                        'ip': c.adresse_ip,
                        'type': c.type_capteur,
                        'zone': c.zone.nom,
                        'derniere_communication': c.date_derniere_communication,
                        'etat': c.etat
                    }
                    for c in capteurs_connectes
                ]
            },
            'capteurs_deconnectes': {
                'nombre': capteurs_deconnectes.count(),
                'liste': [
                    {
                        'id': c.id,
                        'nom': c.nom,
                        'mac': c.adresse_mac,
                        'type': c.type_capteur,
                        'zone': c.zone.nom,
                        'derniere_communication': c.date_derniere_communication,
                        'etat': c.etat
                    }
                    for c in capteurs_deconnectes
                ]
            },
            'timestamp_verification': timezone.now().isoformat()
        }
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Erreur état détection: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la vérification: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def forcer_detection_capteur(request):
    """Force la détection d'un capteur spécifique (pour tests)"""
    try:
        capteur_id = request.data.get('capteur_id')
        adresse_ip = request.data.get('adresse_ip', '127.0.0.1')
        
        if not capteur_id:
            return Response({
                'erreur': 'capteur_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            capteur = CapteurArduino.objects.get(id=capteur_id)
        except CapteurArduino.DoesNotExist:
            return Response({
                'erreur': f'Capteur {capteur_id} non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Forcer la notification de détection
        notifier_capteur_detecte(capteur, adresse_ip)
        
        return Response({
            'message': f'Détection forcée pour le capteur {capteur.nom}',
            'capteur': {
                'id': capteur.id,
                'nom': capteur.nom,
                'mac': capteur.adresse_mac,
                'ip': adresse_ip,
                'etat': capteur.etat
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur détection forcée: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la détection forcée: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def simuler_nouveau_capteur(request):
    """Simule la découverte d'un nouveau capteur (pour tests)"""
    try:
        # Données du nouveau capteur
        mac_address = request.data.get('mac_address', f'AA:BB:CC:DD:EE:{timezone.now().strftime("%H%M")}')
        type_capteur = request.data.get('type_capteur', 'temperature')
        adresse_ip = request.data.get('adresse_ip', '192.168.1.100')
        
        # Vérifier que la zone existe
        zone = Zone.objects.first()
        if not zone:
            return Response({
                'erreur': 'Aucune zone disponible'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Créer le nouveau capteur
        capteur = CapteurArduino.objects.create(
            nom=f"Capteur_Test_{mac_address[-5:].replace(':', '')}",
            type_capteur=type_capteur,
            zone=zone,
            adresse_mac=mac_address,
            adresse_ip=adresse_ip,
            precision=0.1,
            unite_mesure='°C' if type_capteur == 'temperature' else 'unit',
            frequence_mesure_secondes=300,
            etat='actif',
            version_firmware='1.0.0',
            commentaires='Capteur créé pour test de détection'
        )
        
        # Notifier la découverte
        notifier_capteur_nouveau(capteur, adresse_ip)
        
        return Response({
            'message': f'Nouveau capteur simulé: {capteur.nom}',
            'capteur': {
                'id': capteur.id,
                'nom': capteur.nom,
                'mac': capteur.adresse_mac,
                'ip': adresse_ip,
                'type': capteur.type_capteur,
                'zone': capteur.zone.nom
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur simulation nouveau capteur: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la simulation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_recentes(request):
    """Retourne les notifications récentes des capteurs"""
    try:
        # Récupérer les logs récents (dernières 24h)
        depuis = timezone.now() - timedelta(hours=24)
        
        logs = LogCapteurArduino.objects.filter(
            timestamp__gte=depuis
        ).order_by('-timestamp')[:50]
        
        notifications = []
        for log in logs:
            notifications.append({
                'id': log.id,
                'capteur_id': log.capteur.id,
                'capteur_nom': log.capteur.nom,
                'type_evenement': log.type_evenement,
                'niveau': log.niveau,
                'message': log.message,
                'timestamp': log.timestamp,
                'donnees_contexte': log.donnees_contexte
            })
        
        return Response({
            'notifications': notifications,
            'total': len(notifications),
            'periode': '24 dernières heures'
        })
        
    except Exception as e:
        logger.error(f"Erreur notifications récentes: {str(e)}")
        return Response({
            'erreur': f'Erreur lors de la récupération: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# ENDPOINTS COMPATIBLES AVEC VOTRE PROJET ARDUINO
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def recevoir_info_capteur(request):
    """
    Endpoint pour recevoir les informations du capteur (compatible avec votre Arduino)
    POST /api/sensors/info/
    """
    try:
        # Récupérer l'adresse IP source
        adresse_ip_source = request.META.get('REMOTE_ADDR')
        
        # Données attendues de votre Arduino
        sensor_id = request.data.get('sensor_id')
        sensor_type = request.data.get('sensor_type')
        mac_address = request.data.get('mac_address')
        ip_address = request.data.get('ip_address')
        ssid_wifi = request.data.get('ssid_wifi')
        frequence_mesure_secondes = request.data.get('frequence_mesure_secondes', 120)
        precision = request.data.get('precision', 0.1)
        unite_mesure = request.data.get('unite_mesure', '°C/%')
        battery_voltage = request.data.get('battery_voltage', 3.3)
        wifi_signal = request.data.get('wifi_signal', -50)
        
        # Mapper les types Arduino vers les types acceptés par le backend
        type_mapping = {
            'dht11': 'temperature',
            'dht22': 'temperature',
            'rain': 'pluviometrie',
            'water': 'niveau_mer',
            'temperature': 'temperature',
            'humidity': 'humidite',
            'pressure': 'pression',
        }
        sensor_type_mapped = type_mapping.get(sensor_type.lower(), 'temperature')
        
        logger.info(f"Reception info capteur: {sensor_id} - MAC: {mac_address} - Type: {sensor_type} -> {sensor_type_mapped}")
        
        # Chercher ou créer le capteur
        # Assigner automatiquement à une zone par défaut
        zone_defaut = Zone.objects.first()
        if not zone_defaut:
            # Créer une zone par défaut si aucune n'existe
            zone_defaut = Zone.objects.create(
                nom="Zone par défaut",
                superficie_km2=1.0,
                niveau_risque='modere',
                description="Zone par défaut pour les capteurs automatiques"
            )
        
        capteur, created = CapteurArduino.objects.get_or_create(
            adresse_mac=mac_address,
            defaults={
                'nom': f"{sensor_id}",
                'type_capteur': sensor_type_mapped,
                'zone': zone_defaut,
                'adresse_ip': ip_address,
                'ssid_wifi': ssid_wifi,
                'frequence_mesure_secondes': frequence_mesure_secondes,
                'precision': precision,
                'unite_mesure': unite_mesure,
                'etat': 'actif',
                'actif': True
            }
        )
        
        if not created:
            # Mettre à jour les informations
            capteur.adresse_ip = ip_address
            capteur.ssid_wifi = ssid_wifi
            capteur.frequence_mesure_secondes = frequence_mesure_secondes
            capteur.precision = precision
            capteur.unite_mesure = unite_mesure
            capteur.date_derniere_communication = timezone.now()
            capteur.save()
        
        return Response({
            'success': True,
            'message': f'Informations capteur reçues pour {capteur.nom}',
            'capteur_id': capteur.id,
            'created': created,
            'timestamp': str(timezone.now())
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Erreur lors de la réception des infos capteur: {str(e)}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def recevoir_mesures_capteur(request):
    """
    Endpoint pour recevoir les mesures du capteur (compatible avec votre Arduino)
    POST /api/sensors/measurements/
    """
    try:
        # Récupérer l'adresse IP source
        adresse_ip_source = request.META.get('REMOTE_ADDR')
        
        # Données attendues de votre Arduino
        mac_address = request.data.get('mac_address')
        temperature = request.data.get('temperature')
        humidity = request.data.get('humidity')
        rain_percent = request.data.get('rain_percent')  # NOUVEAU
        water_percent = request.data.get('water_percent')  # NOUVEAU
        timestamp = request.data.get('timestamp')
        battery_voltage = request.data.get('battery_voltage', 3.3)
        wifi_signal = request.data.get('wifi_signal', -50)
        cpu_temperature = request.data.get('cpu_temperature', 45.0)
        uptime_seconds = request.data.get('uptime_seconds', 0)
        
        logger.info(f"Reception mesures: MAC {mac_address} - Temp: {temperature}°C - Hum: {humidity}% - Pluie: {rain_percent}% - Eau: {water_percent}%")
        
        # Chercher le capteur
        try:
            capteur = CapteurArduino.objects.get(adresse_mac=mac_address)
        except CapteurArduino.DoesNotExist:
            return Response({
                'success': False,
                'message': f'Capteur avec MAC {mac_address} introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Créer les mesures
        mesures_crees = []
        
        # Mesure température
        if temperature is not None:
            mesure_temp = MesureArduino.objects.create(
                capteur=capteur,
                valeur=temperature,
                unite='°C',
                timestamp=timezone.now(),
                qualite_donnee='bonne',
                source_donnee='capteur_reel',
                est_valide=True,
                donnees_brutes=json.dumps({
                    'temperature': temperature,
                    'battery_voltage': battery_voltage,
                    'wifi_signal': wifi_signal,
                    'cpu_temperature': cpu_temperature,
                    'uptime_seconds': uptime_seconds,
                    'timestamp': timestamp
                }, default=str)
            )
            mesures_crees.append(f"Température: {temperature}°C")
        
        # Mesure humidité
        if humidity is not None:
            mesure_hum = MesureArduino.objects.create(
                capteur=capteur,
                valeur=humidity,
                humidite=humidity,
                unite='%',
                timestamp=timezone.now(),
                qualite_donnee='bonne',
                source_donnee='capteur_reel',
                est_valide=True,
                donnees_brutes=json.dumps({
                    'humidity': humidity,
                    'battery_voltage': battery_voltage,
                    'wifi_signal': wifi_signal,
                    'cpu_temperature': cpu_temperature,
                    'uptime_seconds': uptime_seconds,
                    'timestamp': timestamp
                }, default=str)
            )
            mesures_crees.append(f"Humidité: {humidity}%")
        
        # Mesure pluie (NOUVEAU)
        if rain_percent is not None:
            mesure_pluie = MesureArduino.objects.create(
                capteur=capteur,
                valeur=rain_percent,
                unite='%',
                timestamp=timezone.now(),
                qualite_donnee='bonne',
                source_donnee='capteur_reel',
                est_valide=True,
                donnees_brutes=json.dumps({
                    'rain_percent': rain_percent,
                    'battery_voltage': battery_voltage,
                    'wifi_signal': wifi_signal,
                    'cpu_temperature': cpu_temperature,
                    'uptime_seconds': uptime_seconds,
                    'timestamp': timestamp
                }, default=str)
            )
            mesures_crees.append(f"Pluie: {rain_percent}%")
        
        # Mesure quantité d'eau (NOUVEAU)
        if water_percent is not None:
            mesure_eau = MesureArduino.objects.create(
                capteur=capteur,
                valeur=water_percent,
                unite='%',
                timestamp=timezone.now(),
                qualite_donnee='bonne',
                source_donnee='capteur_reel',
                est_valide=True,
                donnees_brutes=json.dumps({
                    'water_percent': water_percent,
                    'battery_voltage': battery_voltage,
                    'wifi_signal': wifi_signal,
                    'cpu_temperature': cpu_temperature,
                    'uptime_seconds': uptime_seconds,
                    'timestamp': timestamp
                }, default=str)
            )
            mesures_crees.append(f"Quantité d'eau: {water_percent}%")
        
        # Mettre à jour la dernière communication du capteur
        capteur.date_derniere_communication = timezone.now()
        capteur.tension_batterie = battery_voltage
        capteur.niveau_signal_wifi = wifi_signal
        capteur.temperature_cpu = cpu_temperature
        capteur.save()
        
        # Déclencher l'analyse automatique des mesures capteurs
        try:
            from .services_analyse_capteurs import analyse_capteurs_service
            analyse_result = analyse_capteurs_service.analyser_mesures_capteurs(capteur.id)
            logger.info(f"Analyse automatique des capteurs déclenchée: {analyse_result}")
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse automatique des capteurs: {e}")
        
        return Response({
            'success': True,
            'message': f'Mesures reçues pour {capteur.nom}',
            'mesures': mesures_crees,
            'capteur_id': capteur.id,
            'timestamp': str(timezone.now()),
            'analyse_auto': 'déclenchée'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Erreur lors de la réception des mesures: {str(e)}")
        return Response({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
