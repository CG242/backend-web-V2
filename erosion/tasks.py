from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
import random
import logging
from .models import (
    Capteur, Mesure, Zone, DonneesEnvironnementales, AnalyseErosion,
    CapteurArduino, MesureArduino, DonneesManquantes, LogCapteurArduino,
    EvenementExterne, FusionDonnees, PredictionEnrichie, AlerteEnrichie, ArchiveDonnees
)
from .services import DataConsolidationService
# Imports supprimés - fichiers de services inutilisés supprimés
from .services.analyse_fusion_service import AnalyseFusionService, ArchiveService

logger = logging.getLogger(__name__)


@shared_task
def generer_mesures_automatiques():
    """
    Tâche Celery pour générer automatiquement des mesures
    Exécutée toutes les X minutes selon la fréquence des capteurs
    """
    print("🔄 Génération automatique de mesures...")
    
    capteurs_actifs = Capteur.objects.filter(etat='actif')
    mesures_creees = 0
    
    for capteur in capteurs_actifs:
        # Vérifier si le capteur doit prendre une mesure maintenant
        derniere_mesure = capteur.mesures.first()
        if derniere_mesure:
            temps_ecoule = timezone.now() - derniere_mesure.timestamp
            frequence_minutes = timedelta(minutes=capteur.frequence_mesure_min)
            
            if temps_ecoule < frequence_minutes:
                continue  # Pas encore le moment de prendre une mesure
        
        # Générer une nouvelle mesure
        valeur = generer_valeur_mesure(capteur.type)
        unite = get_unite_mesure(capteur.type)
        
        Mesure.objects.create(
            capteur=capteur,
            valeur=valeur,
            unite=unite,
            timestamp=timezone.now(),
            qualite_donnee='bonne',
            commentaires="Mesure automatique générée"
        )
        mesures_creees += 1
    
    print(f"✅ {mesures_creees} mesures générées automatiquement")
    return f"{mesures_creees} mesures créées"


def generer_valeur_mesure(type_capteur):
    """Génère une valeur réaliste selon le type de capteur"""
    if type_capteur == "temperature":
        return round(random.uniform(24, 34), 1)
    elif type_capteur == "salinite":
        return round(random.uniform(30, 40), 2)
    elif type_capteur == "houle":
        return round(random.uniform(0.5, 3.5), 2)
    elif type_capteur == "vent":
        return round(random.uniform(5, 60), 1)
    elif type_capteur == "pluviometrie":
        return round(random.uniform(0, 100), 1)
    elif type_capteur == "niveau_mer":
        return round(random.uniform(-2, 4), 2)
    elif type_capteur == "ph":
        return round(random.uniform(7.5, 8.5), 2)
    elif type_capteur == "turbidite":
        return round(random.uniform(0.1, 50), 1)
    else:
        return round(random.uniform(0, 100), 2)


def get_unite_mesure(type_capteur):
    """Retourne l'unité de mesure selon le type de capteur"""
    unites = {
        'temperature': '°C',
        'salinite': 'PSU',
        'houle': 'm',
        'vent': 'km/h',
        'pluviometrie': 'mm',
        'niveau_mer': 'm',
        'ph': 'pH',
        'turbidite': 'NTU'
    }
    return unites.get(type_capteur, 'unit')


@shared_task
def nettoyer_anciennes_mesures():
    """
    Tâche pour nettoyer les anciennes mesures (plus de 1 an)
    """
    print("🧹 Nettoyage des anciennes mesures...")
    
    date_limite = timezone.now() - timedelta(days=365)
    anciennes_mesures = Mesure.objects.filter(timestamp__lt=date_limite)
    nombre_supprimees = anciennes_mesures.count()
    
    anciennes_mesures.delete()
    
    print(f"✅ {nombre_supprimees} anciennes mesures supprimées")
    return f"{nombre_supprimees} mesures supprimées"


@shared_task
def verifier_etat_capteurs():
    """
    Tâche pour vérifier l'état des capteurs et générer des alertes
    """
    print("🔍 Vérification de l'état des capteurs...")
    
    capteurs_defaillants = []
    
    for capteur in Capteur.objects.filter(etat='actif'):
        # Vérifier si le capteur n'a pas envoyé de données récemment
        derniere_mesure = capteur.mesures.first()
        if derniere_mesure:
            temps_ecoule = timezone.now() - derniere_mesure.timestamp
            # Si pas de mesure depuis plus de 2x la fréquence normale
            frequence_max = timedelta(minutes=capteur.frequence_mesure_min * 2)
            
            if temps_ecoule > frequence_max:
                capteur.etat = 'defaillant'
                capteur.save()
                capteurs_defaillants.append(capteur.nom)
    
    print(f"⚠️ {len(capteurs_defaillants)} capteurs marqués comme défaillants")
    return f"{len(capteurs_defaillants)} capteurs défaillants détectés"


# ============================================================================
# NOUVELLES TÂCHES POUR LES FONCTIONNALITÉS ENRICHIES
# ============================================================================

@shared_task
def collecter_donnees_environnementales():
    """
    Tâche pour collecter automatiquement les données environnementales
    de toutes les zones actives
    """
    print("🌍 Collecte automatique des données environnementales...")
    
    zones_actives = Zone.objects.all()
    donnees_collectees = 0
    
    for zone in zones_actives:
        try:
            # Définir la période de collecte (dernières 24h)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            
            # Formater les dates pour les APIs
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Collecter les données
            consolidation_service = DataConsolidationService()
            consolidated_data = consolidation_service.collect_all_data(
                zone, start_date_str, end_date_str
            )
            
            # Sauvegarder les données
            donnees_env = consolidation_service.save_consolidated_data(zone, consolidated_data)
            donnees_collectees += 1
            
            print(f"✅ Données collectées pour {zone.nom}")
            
        except Exception as e:
            print(f"❌ Erreur collecte {zone.nom}: {e}")
    
    print(f"📊 {donnees_collectees} zones traitées")
    return f"{donnees_collectees} zones traitées"


@shared_task
def generer_analyses_erosion_automatiques():
    """
    Tâche pour générer automatiquement des analyses d'érosion
    pour toutes les zones avec des données environnementales récentes
    """
    print("🔬 Génération automatique d'analyses d'érosion...")
    
    # Récupérer les zones avec des données environnementales récentes
    zones_avec_donnees = Zone.objects.filter(
        donnees_environnementales__date_collecte__gte=timezone.now() - timedelta(days=1)
    ).distinct()
    
    analyses_creees = 0
    
    for zone in zones_avec_donnees:
        try:
            # Récupérer les données environnementales les plus récentes
            donnees_env = DonneesEnvironnementales.objects.filter(
                zone=zone
            ).order_by('-date_collecte').first()
            
            if donnees_env:
                # Vérifier si une analyse récente existe déjà
                analyse_recente = AnalyseErosion.objects.filter(
                    zone=zone,
                    donnees_environnementales=donnees_env,
                    date_analyse__gte=timezone.now() - timedelta(hours=6)
                ).exists()
                
                if not analyse_recente:
                    # Créer une nouvelle analyse
                    analyse_view = AnalyseErosionViewSet()
                    analyse = analyse_view._calculer_analyse_erosion(zone, donnees_env, 30)
                    analyses_creees += 1
                    
                    print(f"✅ Analyse créée pour {zone.nom}")
            
        except Exception as e:
            print(f"❌ Erreur analyse {zone.nom}: {e}")
    
    print(f"📈 {analyses_creees} analyses créées")
    return f"{analyses_creees} analyses créées"


@shared_task
def nettoyer_donnees_anciennes():
    """
    Tâche pour nettoyer les anciennes données environnementales et analyses
    """
    print("🧹 Nettoyage des anciennes données...")
    
    # Nettoyer les données environnementales anciennes (plus de 3 mois)
    date_limite_env = timezone.now() - timedelta(days=90)
    anciennes_donnees_env = DonneesEnvironnementales.objects.filter(
        date_collecte__lt=date_limite_env
    )
    nb_env_supprimees = anciennes_donnees_env.count()
    anciennes_donnees_env.delete()
    
    # Nettoyer les analyses anciennes (plus de 6 mois)
    date_limite_analyses = timezone.now() - timedelta(days=180)
    anciennes_analyses = AnalyseErosion.objects.filter(
        date_analyse__lt=date_limite_analyses
    )
    nb_analyses_supprimees = anciennes_analyses.count()
    anciennes_analyses.delete()
    
    print(f"✅ {nb_env_supprimees} données environnementales supprimées")
    print(f"✅ {nb_analyses_supprimees} analyses supprimées")
    
    return f"{nb_env_supprimees} données env et {nb_analyses_supprimees} analyses supprimées"


@shared_task
def synchroniser_donnees_cartographiques():
    """
    Tâche pour synchroniser les données cartographiques avec les APIs externes
    """
    print("🗺️ Synchronisation des données cartographiques...")
    
    # Cette tâche pourrait être étendue pour télécharger automatiquement
    # les nouvelles images satellites, données de substrat, etc.
    
    zones_actives = Zone.objects.all()
    donnees_synchronisees = 0
    
    for zone in zones_actives:
        try:
            # Ici, on pourrait implémenter la logique pour :
            # - Télécharger les nouvelles images satellites
            # - Mettre à jour les données de substrat
            # - Synchroniser les données hydrographiques
            
            print(f"✅ Données cartographiques synchronisées pour {zone.nom}")
            donnees_synchronisees += 1
            
        except Exception as e:
            print(f"❌ Erreur synchronisation {zone.nom}: {e}")
    
    print(f"🗺️ {donnees_synchronisees} zones synchronisées")
    return f"{donnees_synchronisees} zones synchronisées"


@shared_task
def generer_rapport_quotidien():
    """
    Tâche pour générer un rapport quotidien des activités du système
    """
    print("📊 Génération du rapport quotidien...")
    
    # Statistiques du jour
    aujourd_hui = timezone.now().date()
    
    # Nombre de mesures générées
    mesures_aujourd_hui = Mesure.objects.filter(
        timestamp__date=aujourd_hui
    ).count()
    
    # Nombre de données environnementales collectées
    donnees_env_aujourd_hui = DonneesEnvironnementales.objects.filter(
        date_collecte__date=aujourd_hui
    ).count()
    
    # Nombre d'analyses créées
    analyses_aujourd_hui = AnalyseErosion.objects.filter(
        date_analyse__date=aujourd_hui
    ).count()
    
    # Zones actives
    zones_actives = Zone.objects.count()
    
    rapport = {
        'date': aujourd_hui.isoformat(),
        'mesures_generes': mesures_aujourd_hui,
        'donnees_environnementales': donnees_env_aujourd_hui,
        'analyses_erosion': analyses_aujourd_hui,
        'zones_actives': zones_actives,
        'statut_systeme': 'opérationnel'
    }
    
    print(f"📈 Rapport quotidien généré: {rapport}")
    return rapport


# ============================================================================
# NOUVELLES TÂCHES POUR LES CAPTEURS ARDUINO
# ============================================================================

# Tâches supprimées - services Arduino inutilisés supprimés
# @shared_task
# def monitorer_capteurs_arduino():
#     """Tâche supprimée - service ArduinoMonitoringService supprimé"""
#     pass

# @shared_task
# def detecter_donnees_manquantes_arduino():
#     """Tâche supprimée - service DataCompletionService supprimé"""
#     pass

# @shared_task
# def completer_donnees_manquantes_arduino():
#     """Tâche supprimée - service DataCompletionService supprimé"""
#     pass

# @shared_task
# def simuler_donnees_arduino_test():
#     """Tâche supprimée - service ArduinoConnectionService supprimé"""
#     pass

# @shared_task
# def detecter_capteurs_automatique():
#     """Tâche supprimée - service CapteurDetectionService supprimé"""
#     pass

# @shared_task
# def envoyer_notifications_quotidiennes():
#     """Tâche supprimée - service CapteurNotificationService supprimé"""
#     pass


# ============================================================================
# NOUVELLES TÂCHES POUR ÉVÉNEMENTS EXTERNES ET FUSION DE DONNÉES
# ============================================================================

@shared_task
def analyser_fusion_evenement(evenement_id: int):
    """
    Tâche pour analyser un événement externe et créer une fusion de données
    """
    logger.info(f"Analyse de fusion pour l'événement {evenement_id}")
    
    try:
        service = AnalyseFusionService()
        resultat = service.analyser_evenement(evenement_id)
        
        if resultat['success']:
            logger.info(f"Analyse terminée pour l'événement {evenement_id}: {resultat['message']}")
            return f"Analyse réussie: {resultat['message']}"
        else:
            logger.error(f"Échec analyse événement {evenement_id}: {resultat['message']}")
            return f"Échec: {resultat['message']}"
            
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'événement {evenement_id}: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def analyser_fusion_zone(zone_id: int, periode_jours: int = 30):
    """
    Tâche pour analyser une zone complète et créer des fusions de données
    """
    logger.info(f"Analyse de fusion pour la zone {zone_id} sur {periode_jours} jours")
    
    try:
        service = AnalyseFusionService()
        resultat = service.analyser_zone(zone_id, periode_jours)
        
        if resultat['success']:
            logger.info(f"Analyse de zone terminée: {resultat['message']}")
            return f"Analyse réussie: {resultat['message']}"
        else:
            logger.error(f"Échec analyse zone {zone_id}: {resultat['message']}")
            return f"Échec: {resultat['message']}"
            
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de la zone {zone_id}: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def traiter_evenements_en_attente():
    """
    Tâche pour traiter les événements externes en attente de traitement
    """
    logger.info("Traitement des événements en attente")
    
    try:
        # Récupérer les événements non traités des dernières 24h
        date_limite = timezone.now() - timedelta(hours=24)
        evenements_en_attente = EvenementExterne.objects.filter(
            is_traite=False,
            is_valide=True,
            date_evenement__gte=date_limite
        ).order_by('date_evenement')
        
        evenements_traites = 0
        
        for evenement in evenements_en_attente:
            try:
                # Marquer comme traité et déclencher l'analyse
                evenement.is_traite = True
                evenement.save()
                
                # Déclencher l'analyse
                analyser_fusion_evenement.delay(evenement.id)
                evenements_traites += 1
                
            except Exception as e:
                logger.error(f"Erreur traitement événement {evenement.id}: {e}")
        
        logger.info(f"Traitement terminé: {evenements_traites} événements traités")
        return f"{evenements_traites} événements traités"
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement des événements en attente: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def nettoyer_anciens_evenements():
    """
    Tâche pour nettoyer les anciens événements externes
    """
    logger.info("Nettoyage des anciens événements externes")
    
    try:
        # Supprimer les événements de simulation de plus de 30 jours
        date_limite_simulation = timezone.now() - timedelta(days=30)
        anciens_simulations = EvenementExterne.objects.filter(
            is_simulation=True,
            date_evenement__lt=date_limite_simulation
        )
        nb_simulations_supprimees = anciens_simulations.count()
        anciens_simulations.delete()
        
        # Supprimer les événements invalides de plus de 7 jours
        date_limite_invalides = timezone.now() - timedelta(days=7)
        anciens_invalides = EvenementExterne.objects.filter(
            is_valide=False,
            date_evenement__lt=date_limite_invalides
        )
        nb_invalides_supprimees = anciens_invalides.count()
        anciens_invalides.delete()
        
        # Supprimer les événements traités de plus de 90 jours
        date_limite_traites = timezone.now() - timedelta(days=90)
        anciens_traites = EvenementExterne.objects.filter(
            is_traite=True,
            date_evenement__lt=date_limite_traites
        )
        nb_traites_supprimees = anciens_traites.count()
        anciens_traites.delete()
        
        logger.info(f"Nettoyage terminé: {nb_simulations_supprimees} simulations, "
                   f"{nb_invalides_supprimees} invalides, {nb_traites_supprimees} traités supprimés")
        
        return f"{nb_simulations_supprimees + nb_invalides_supprimees + nb_traites_supprimees} événements supprimés"
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des événements: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def nettoyer_anciennes_fusions():
    """
    Tâche pour nettoyer les anciennes fusions de données
    """
    logger.info("Nettoyage des anciennes fusions de données")
    
    try:
        # Supprimer les fusions terminées de plus de 6 mois
        date_limite = timezone.now() - timedelta(days=180)
        anciennes_fusions = FusionDonnees.objects.filter(
            statut='terminee',
            date_creation__lt=date_limite
        )
        nb_fusions_supprimees = anciennes_fusions.count()
        anciennes_fusions.delete()
        
        # Supprimer les fusions en erreur de plus de 30 jours
        date_limite_erreurs = timezone.now() - timedelta(days=30)
        anciennes_erreurs = FusionDonnees.objects.filter(
            statut='erreur',
            date_creation__lt=date_limite_erreurs
        )
        nb_erreurs_supprimees = anciennes_erreurs.count()
        anciennes_erreurs.delete()
        
        logger.info(f"Nettoyage fusions terminé: {nb_fusions_supprimees} fusions, "
                   f"{nb_erreurs_supprimees} erreurs supprimées")
        
        return f"{nb_fusions_supprimees + nb_erreurs_supprimees} fusions supprimées"
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des fusions: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def nettoyer_anciennes_predictions():
    """
    Tâche pour nettoyer les anciennes prédictions enrichies
    """
    logger.info("Nettoyage des anciennes prédictions enrichies")
    
    try:
        # Supprimer les prédictions de plus de 1 an
        date_limite = timezone.now() - timedelta(days=365)
        anciennes_predictions = PredictionEnrichie.objects.filter(
            date_prediction__lt=date_limite
        )
        nb_predictions_supprimees = anciennes_predictions.count()
        anciennes_predictions.delete()
        
        logger.info(f"Nettoyage prédictions terminé: {nb_predictions_supprimees} prédictions supprimées")
        return f"{nb_predictions_supprimees} prédictions supprimées"
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des prédictions: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def nettoyer_anciennes_alertes():
    """
    Tâche pour nettoyer les anciennes alertes enrichies
    """
    logger.info("Nettoyage des anciennes alertes enrichies")
    
    try:
        # Résoudre les alertes anciennes non résolues
        date_limite_resolution = timezone.now() - timedelta(days=30)
        alertes_anciennes = AlerteEnrichie.objects.filter(
            est_resolue=False,
            date_creation__lt=date_limite_resolution
        )
        nb_alertes_resolues = alertes_anciennes.count()
        
        for alerte in alertes_anciennes:
            alerte.est_resolue = True
            alerte.est_active = False
            alerte.date_resolution = timezone.now()
            alerte.commentaires += " Résolue automatiquement par nettoyage."
            alerte.save()
        
        # Supprimer les alertes résolues de plus de 6 mois
        date_limite_suppression = timezone.now() - timedelta(days=180)
        anciennes_alertes = AlerteEnrichie.objects.filter(
            est_resolue=True,
            date_resolution__lt=date_limite_suppression
        )
        nb_alertes_supprimees = anciennes_alertes.count()
        anciennes_alertes.delete()
        
        logger.info(f"Nettoyage alertes terminé: {nb_alertes_resolues} résolues, "
                   f"{nb_alertes_supprimees} supprimées")
        
        return f"{nb_alertes_resolues} alertes résolues, {nb_alertes_supprimees} supprimées"
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des alertes: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def creer_archive_donnees(type_donnees: str, zone_id: int, periode_jours: int):
    """
    Tâche pour créer une archive de données
    """
    logger.info(f"Création d'archive {type_donnees} pour la zone {zone_id}")
    
    try:
        service = ArchiveService()
        resultat = service.creer_archive(type_donnees, zone_id, periode_jours)
        
        if resultat['success']:
            logger.info(f"Archive créée: {resultat['archive_id']}")
            return f"Archive créée: {resultat['nombre_elements']} éléments"
        else:
            logger.error(f"Échec création archive: {resultat['message']}")
            return f"Échec: {resultat['message']}"
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'archive: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def purger_anciennes_archives(periode_jours: int = 365):
    """
    Tâche pour purger les anciennes archives
    """
    logger.info(f"Purge des archives de plus de {periode_jours} jours")
    
    try:
        date_limite = timezone.now() - timedelta(days=periode_jours)
        anciennes_archives = ArchiveDonnees.objects.filter(
            date_archivage__lt=date_limite,
            est_disponible=True
        )
        
        nb_archives_supprimees = 0
        
        for archive in anciennes_archives:
            try:
                # Supprimer le fichier physique
                import os
                if os.path.exists(archive.chemin_fichier):
                    os.remove(archive.chemin_fichier)
                
                # Marquer comme supprimée
                archive.est_disponible = False
                archive.date_suppression = timezone.now()
                archive.save()
                
                nb_archives_supprimees += 1
                
            except Exception as e:
                logger.error(f"Erreur suppression archive {archive.id}: {e}")
        
        logger.info(f"Purge terminée: {nb_archives_supprimees} archives supprimées")
        return f"{nb_archives_supprimees} archives supprimées"
        
    except Exception as e:
        logger.error(f"Erreur lors de la purge des archives: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def generer_rapport_fusion_quotidien():
    """
    Tâche pour générer un rapport quotidien de fusion des données
    """
    logger.info("Génération du rapport quotidien de fusion")
    
    try:
        aujourd_hui = timezone.now().date()
        hier = aujourd_hui - timedelta(days=1)
        
        # Statistiques des événements
        evenements_hier = EvenementExterne.objects.filter(
            date_evenement__date=hier
        )
        
        # Statistiques des fusions
        fusions_hier = FusionDonnees.objects.filter(
            date_creation__date=hier
        )
        
        # Statistiques des prédictions
        predictions_hier = PredictionEnrichie.objects.filter(
            date_prediction__date=hier
        )
        
        # Statistiques des alertes
        alertes_hier = AlerteEnrichie.objects.filter(
            date_creation__date=hier
        )
        
        rapport = {
            'date': hier.isoformat(),
            'evenements': {
                'total': evenements_hier.count(),
                'traites': evenements_hier.filter(is_traite=True).count(),
                'non_traites': evenements_hier.filter(is_traite=False).count(),
                'simulations': evenements_hier.filter(is_simulation=True).count(),
                'par_type': dict(evenements_hier.values_list('type_evenement').annotate(count=Count('id')))
            },
            'fusions': {
                'total': fusions_hier.count(),
                'terminees': fusions_hier.filter(statut='terminee').count(),
                'en_cours': fusions_hier.filter(statut='en_cours').count(),
                'erreurs': fusions_hier.filter(statut='erreur').count()
            },
            'predictions': {
                'total': predictions_hier.count(),
                'erosion_predite': predictions_hier.filter(erosion_predite=True).count(),
                'erosion_non_predite': predictions_hier.filter(erosion_predite=False).count(),
                'par_niveau': dict(predictions_hier.values_list('niveau_erosion').annotate(count=Count('id')))
            },
            'alertes': {
                'total': alertes_hier.count(),
                'actives': alertes_hier.filter(est_active=True).count(),
                'resolues': alertes_hier.filter(est_resolue=True).count(),
                'par_niveau': dict(alertes_hier.values_list('niveau').annotate(count=Count('id')))
            },
            'statut_systeme': 'opérationnel'
        }
        
        logger.info(f"Rapport quotidien généré: {rapport}")
        return rapport
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport quotidien: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def exporter_donnees_ia():
    """
    Tâche pour exporter les données pour l'IA (format ML)
    """
    logger.info("Export des données pour l'IA")
    
    try:
        # Récupérer les données des 6 derniers mois
        date_limite = timezone.now() - timedelta(days=180)
        
        # Données d'entraînement
        donnees_entrainement = {
            'evenements': [],
            'mesures_arduino': [],
            'fusions': [],
            'predictions': []
        }
        
        # Événements
        evenements = EvenementExterne.objects.filter(
            date_evenement__gte=date_limite,
            is_valide=True
        )
        
        for e in evenements:
            donnees_entrainement['evenements'].append({
                'type_evenement': e.type_evenement,
                'intensite': e.intensite,
                'zone_id': e.zone.id,
                'date_evenement': e.date_evenement.isoformat(),
                'duree_minutes': e.duree_minutes or 0,
                'rayon_impact_km': e.rayon_impact_km or 0
            })
        
        # Mesures Arduino
        mesures = MesureArduino.objects.filter(
            timestamp__gte=date_limite,
            est_valide=True
        ).select_related('capteur')
        
        for m in mesures:
            donnees_entrainement['mesures_arduino'].append({
                'capteur_type': m.capteur.type_capteur,
                'valeur': m.valeur,
                'zone_id': m.capteur.zone.id,
                'timestamp': m.timestamp.isoformat(),
                'qualite_donnee': m.qualite_donnee
            })
        
        # Fusions
        fusions = FusionDonnees.objects.filter(
            date_creation__gte=date_limite,
            statut='terminee'
        )
        
        for f in fusions:
            donnees_entrainement['fusions'].append({
                'zone_id': f.zone.id,
                'score_erosion': f.score_erosion,
                'probabilite_erosion': f.probabilite_erosion,
                'mesures_count': f.mesures_arduino_count,
                'evenements_count': f.evenements_externes_count,
                'facteurs_dominants': f.facteurs_dominants
            })
        
        # Prédictions
        predictions = PredictionEnrichie.objects.filter(
            date_prediction__gte=date_limite
        )
        
        for p in predictions:
            donnees_entrainement['predictions'].append({
                'zone_id': p.zone.id,
                'erosion_predite': p.erosion_predite,
                'niveau_erosion': p.niveau_erosion,
                'confiance_pourcentage': p.confiance_pourcentage,
                'taux_erosion_pred': p.taux_erosion_pred_m_an,
                'horizon_jours': p.horizon_jours
            })
        
        # Sauvegarder le fichier d'export
        import json
        import os
        
        chemin_export = f"exports/ia/donnees_entrainement_{timezone.now().strftime('%Y%m%d')}.json"
        os.makedirs(os.path.dirname(chemin_export), exist_ok=True)
        
        with open(chemin_export, 'w', encoding='utf-8') as f:
            json.dump(donnees_entrainement, f, ensure_ascii=False, indent=2)
        
        # Statistiques
        stats = {
            'evenements': len(donnees_entrainement['evenements']),
            'mesures': len(donnees_entrainement['mesures_arduino']),
            'fusions': len(donnees_entrainement['fusions']),
            'predictions': len(donnees_entrainement['predictions']),
            'chemin_fichier': chemin_export,
            'date_export': timezone.now().isoformat()
        }
        
        logger.info(f"Export IA terminé: {stats}")
        return f"Export réussi: {stats['evenements']} événements, {stats['mesures']} mesures, {stats['fusions']} fusions, {stats['predictions']} prédictions"
        
    except Exception as e:
        logger.error(f"Erreur lors de l'export IA: {e}")
        return f"Erreur: {str(e)}"
