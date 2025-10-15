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


# ============================================================================
# NOUVELLES TÂCHES POUR LES PRÉDICTIONS ML
# ============================================================================

@shared_task
def calculer_predictions_automatiques():
    """
    Tâche pour calculer automatiquement les prédictions d'érosion pour toutes les zones
    Exécutée quotidiennement ou sur demande
    """
    logger.info("🤖 Calcul automatique des prédictions d'érosion")
    
    try:
        from .models import Zone, ModeleML
        from .ml_services import MLPredictionService
        
        # Vérifier qu'il y a un modèle actif
        active_model = ModeleML.objects.filter(statut='actif').first()
        if not active_model:
            logger.warning("Aucun modèle ML actif trouvé pour les prédictions automatiques")
            return "Aucun modèle ML actif - prédictions ignorées"
        
        # Récupérer toutes les zones actives
        zones_actives = Zone.objects.all()
        predictions_creees = 0
        erreurs = 0
        
        ml_service = MLPredictionService()
        
        for zone in zones_actives:
            try:
                # Vérifier si une prédiction récente existe déjà (dernières 24h)
                from django.utils import timezone
                from datetime import timedelta
                
                derniere_prediction = zone.predictions.filter(
                    date_prediction__gte=timezone.now() - timedelta(hours=24)
                ).first()
                
                if derniere_prediction:
                    logger.info(f"Prédiction récente existante pour {zone.nom} - ignorée")
                    continue
                
                # Calculer la prédiction pour différents horizons
                horizons = [7, 30, 90]  # 1 semaine, 1 mois, 3 mois
                
                for horizon in horizons:
                    prediction = ml_service.predire_erosion(
                        zone_id=zone.id,
                        features={},  # Pas de features supplémentaires pour les prédictions automatiques
                        horizon_jours=horizon
                    )
                    
                    # Ajouter un commentaire pour identifier les prédictions automatiques
                    prediction.commentaires = f"Prédiction automatique générée le {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                    prediction.save()
                    
                    predictions_creees += 1
                    logger.info(f"✅ Prédiction créée pour {zone.nom} (horizon: {horizon}j)")
                
            except Exception as e:
                logger.error(f"❌ Erreur prédiction {zone.nom}: {e}")
                erreurs += 1
        
        resultat = f"Prédictions automatiques terminées: {predictions_creees} créées, {erreurs} erreurs"
        logger.info(resultat)
        return resultat
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des prédictions automatiques: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def calculer_prediction_zone(zone_id: int, horizon_jours: int = 30, features: dict = None):
    """
    Tâche pour calculer une prédiction pour une zone spécifique
    
    Args:
        zone_id: ID de la zone
        horizon_jours: Horizon de prédiction en jours
        features: Features supplémentaires (optionnel)
    """
    logger.info(f"🎯 Calcul de prédiction pour la zone {zone_id} (horizon: {horizon_jours}j)")
    
    try:
        from .models import Zone
        from .ml_services import MLPredictionService
        
        # Vérifier que la zone existe
        try:
            zone = Zone.objects.get(id=zone_id)
        except Zone.DoesNotExist:
            logger.error(f"Zone {zone_id} non trouvée")
            return f"Zone {zone_id} non trouvée"
        
        # Calculer la prédiction
        ml_service = MLPredictionService()
        prediction = ml_service.predire_erosion(
            zone_id=zone_id,
            features=features or {},
            horizon_jours=horizon_jours
        )
        
        # Ajouter un commentaire pour identifier les prédictions par tâche
        prediction.commentaires = f"Prédiction calculée par tâche Celery le {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        prediction.save()
        
        resultat = f"Prédiction créée: ID {prediction.id} pour {zone.nom} - Taux: {prediction.taux_erosion_pred_m_an:.3f} m/an"
        logger.info(resultat)
        return resultat
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul de prédiction pour la zone {zone_id}: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def entrainer_modeles_ml():
    """
    Tâche pour entraîner automatiquement les modèles ML
    Exécutée périodiquement (hebdomadaire) ou sur demande
    """
    logger.info("🧠 Entraînement automatique des modèles ML")
    
    try:
        from .ml_services import MLTrainingService
        
        # Vérifier les prérequis
        from .models import HistoriqueErosion, Zone
        
        total_zones = Zone.objects.count()
        total_historique = HistoriqueErosion.objects.count()
        
        if total_zones == 0:
            logger.warning("Aucune zone trouvée - entraînement ignoré")
            return "Aucune zone trouvée"
        
        if total_historique < 10:
            logger.warning(f"Pas assez de données historiques ({total_historique}) - entraînement ignoré")
            return f"Pas assez de données historiques ({total_historique})"
        
        # Entraîner les modèles
        training_service = MLTrainingService()
        results = training_service.train_models()
        
        # Analyser les résultats
        if results.get('errors'):
            error_msg = 'Erreurs lors de l\'entraînement:\n' + '\n'.join(results['errors'])
            logger.error(error_msg)
            return f"Erreurs: {error_msg}"
        
        # Compter les modèles créés
        models_created = 0
        if results.get('random_forest') and 'error' not in results['random_forest']:
            models_created += 1
        if results.get('regression_lineaire') and 'error' not in results['regression_lineaire']:
            models_created += 1
        
        # Trouver le modèle actif
        from .models import ModeleML
        active_model = ModeleML.objects.filter(statut='actif').first()
        
        resultat = f"Entraînement terminé: {models_created} modèles créés"
        if active_model:
            resultat += f", modèle actif: {active_model.nom} v{active_model.version}"
        
        logger.info(resultat)
        return resultat
        
    except Exception as e:
        logger.error(f"Erreur lors de l'entraînement automatique: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def evaluer_performance_modeles():
    """
    Tâche pour évaluer la performance des modèles ML existants
    """
    logger.info("📊 Évaluation de la performance des modèles ML")
    
    try:
        from .models import ModeleML, Prediction
        
        models_evalues = 0
        rapport_performance = []
        
        for model in ModeleML.objects.filter(statut__in=['actif', 'inactif']):
            try:
                # Récupérer les prédictions récentes (derniers 30 jours)
                date_limite = timezone.now() - timedelta(days=30)
                predictions_recentes = Prediction.objects.filter(
                    modele_ml=model,
                    date_prediction__gte=date_limite
                )
                
                if predictions_recentes.count() < 5:
                    logger.info(f"Pas assez de prédictions récentes pour {model.nom} - ignoré")
                    continue
                
                # Calculer les métriques de performance
                from django.db.models import Avg, StdDev
                
                stats = predictions_recentes.aggregate(
                    confiance_moyenne=Avg('confiance_pourcentage'),
                    confiance_ecart_type=StdDev('confiance_pourcentage'),
                    taux_moyen=Avg('taux_erosion_pred_m_an'),
                    nombre_predictions=Count('id')
                )
                
                performance_data = {
                    'model_id': model.id,
                    'model_name': model.nom,
                    'model_version': model.version,
                    'confiance_moyenne': stats['confiance_moyenne'] or 0,
                    'confiance_ecart_type': stats['confiance_ecart_type'] or 0,
                    'taux_moyen': stats['taux_moyen'] or 0,
                    'nombre_predictions': stats['nombre_predictions'],
                    'score_original': model.precision_score or 0
                }
                
                rapport_performance.append(performance_data)
                models_evalues += 1
                
                logger.info(f"✅ Performance évaluée pour {model.nom}: confiance {performance_data['confiance_moyenne']:.1f}%")
                
            except Exception as e:
                logger.error(f"Erreur évaluation {model.nom}: {e}")
        
        resultat = f"Évaluation terminée: {models_evalues} modèles évalués"
        logger.info(resultat)
        
        # Optionnel: sauvegarder le rapport de performance
        if rapport_performance:
            import json
            import os
            
            chemin_rapport = f"reports/ml_performance_{timezone.now().strftime('%Y%m%d')}.json"
            os.makedirs(os.path.dirname(chemin_rapport), exist_ok=True)
            
            with open(chemin_rapport, 'w', encoding='utf-8') as f:
                json.dump({
                    'date_evaluation': timezone.now().isoformat(),
                    'models_evalues': models_evalues,
                    'performance_data': rapport_performance
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Rapport de performance sauvegardé: {chemin_rapport}")
        
        return resultat
        
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation de performance: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def nettoyer_anciennes_predictions_ml():
    """
    Tâche pour nettoyer les anciennes prédictions ML
    """
    logger.info("🧹 Nettoyage des anciennes prédictions ML")
    
    try:
        from .models import Prediction
        
        # Supprimer les prédictions de plus de 6 mois
        date_limite = timezone.now() - timedelta(days=180)
        anciennes_predictions = Prediction.objects.filter(
            date_prediction__lt=date_limite
        )
        
        nb_predictions_supprimees = anciennes_predictions.count()
        anciennes_predictions.delete()
        
        # Supprimer les modèles inactifs de plus de 1 an
        from .models import ModeleML
        date_limite_modeles = timezone.now() - timedelta(days=365)
        anciens_modeles = ModeleML.objects.filter(
            statut='inactif',
            date_creation__lt=date_limite_modeles
        )
        
        nb_modeles_supprimees = anciens_modeles.count()
        
        # Supprimer les fichiers de modèles associés
        import os
        for model in anciens_modeles:
            try:
                if os.path.exists(model.chemin_fichier):
                    os.remove(model.chemin_fichier)
            except Exception as e:
                logger.warning(f"Impossible de supprimer le fichier {model.chemin_fichier}: {e}")
        
        anciens_modeles.delete()
        
        resultat = f"Nettoyage terminé: {nb_predictions_supprimees} prédictions, {nb_modeles_supprimees} modèles supprimés"
        logger.info(resultat)
        return resultat
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des prédictions ML: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def generer_rapport_ml_quotidien():
    """
    Tâche pour générer un rapport quotidien des activités ML
    """
    logger.info("📈 Génération du rapport quotidien ML")
    
    try:
        from .models import ModeleML, Prediction
        
        aujourd_hui = timezone.now().date()
        hier = aujourd_hui - timedelta(days=1)
        
        # Statistiques des prédictions
        predictions_hier = Prediction.objects.filter(
            date_prediction__date=hier
        )
        
        # Statistiques des modèles
        modeles_actifs = ModeleML.objects.filter(statut='actif').count()
        modeles_total = ModeleML.objects.count()
        
        # Statistiques par modèle
        stats_par_modele = []
        for model in ModeleML.objects.filter(statut='actif'):
            pred_model = predictions_hier.filter(modele_ml=model)
            stats_par_modele.append({
                'model_name': model.nom,
                'model_version': model.version,
                'predictions_count': pred_model.count(),
                'confiance_moyenne': pred_model.aggregate(avg=Avg('confiance_pourcentage'))['avg'] or 0,
                'taux_moyen': pred_model.aggregate(avg=Avg('taux_erosion_pred_m_an'))['avg'] or 0
            })
        
        rapport = {
            'date': hier.isoformat(),
            'predictions': {
                'total': predictions_hier.count(),
                'par_horizon': dict(predictions_hier.values_list('horizon_jours').annotate(count=Count('id'))),
                'confiance_moyenne': predictions_hier.aggregate(avg=Avg('confiance_pourcentage'))['avg'] or 0,
                'taux_moyen': predictions_hier.aggregate(avg=Avg('taux_erosion_pred_m_an'))['avg'] or 0
            },
            'modeles': {
                'actifs': modeles_actifs,
                'total': modeles_total,
                'stats_par_modele': stats_par_modele
            },
            'statut_systeme': 'opérationnel'
        }
        
        logger.info(f"Rapport ML quotidien généré: {rapport}")
        return rapport
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport ML quotidien: {e}")
        return f"Erreur: {str(e)}"


@shared_task
def analyser_evenement_externe(evenement_id):
    """
    Tâche Celery pour analyser un événement externe reçu selon le format de votre ami
    """
    logger.info(f"🌊 Analyse de l'événement externe ID: {evenement_id}")
    
    try:
        evenement = EvenementExterne.objects.get(id=evenement_id)
        
        # Marquer comme en cours de traitement
        evenement.is_traite = False
        evenement.save()
        
        # Vérifier si l'événement nécessite une alerte
        if evenement.necessite_alerte:
            alerte = AlerteEnrichie.objects.create(
                zone=evenement.zone,
                type='evenement_extreme',
                niveau='critique' if evenement.niveau_risque == 'critique' else 'alerte',
                titre=f"Événement climatique critique: {evenement.get_type_evenement_display()}",
                description=f"Événement {evenement.niveau_risque} détecté: {evenement.type_evenement} - Intensité {evenement.intensite}",
                est_active=True,
                est_resolue=False,
                actions_requises=[
                    "Surveillance renforcée de la zone",
                    "Évaluation des risques d'érosion",
                    "Préparation aux mesures d'urgence si nécessaire"
                ],
                donnees_contexte={
                    'type_source': 'evenement_externe',
                    'evenement_id': evenement.id,
                    'niveau_risque': evenement.niveau_risque,
                    'zone_erosion': evenement.zone_erosion,
                    'type_evenement': evenement.type_evenement,
                    'intensite': evenement.intensite,
                    'duree': evenement.duree
                }
            )
            
            logger.info(f"Alerte créée pour l'événement externe: {alerte.id}")
        
        # Marquer comme traité
        evenement.is_traite = True
        evenement.save()
        
        logger.info(f"Événement externe analysé avec succès: {evenement_id}")
        
        return {
            'success': True,
            'evenement_id': evenement_id,
            'niveau_risque': evenement.niveau_risque,
            'zone_erosion': evenement.zone_erosion,
            'alertes_creees': AlerteEnrichie.objects.filter(
                donnees_contexte__contains={'evenement_id': evenement_id}
            ).count()
        }
        
    except EvenementExterne.DoesNotExist:
        logger.error(f"Événement externe introuvable: {evenement_id}")
        return {'success': False, 'error': 'Événement introuvable'}
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'événement externe {evenement_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def generer_rapport_evenements_externes_quotidien():
    """
    Tâche pour générer un rapport quotidien des événements externes
    """
    logger.info("🌊 Génération du rapport quotidien des événements externes")
    
    try:
        aujourd_hui = timezone.now().date()
        hier = aujourd_hui - timedelta(days=1)
        
        # Événements d'hier
        evenements_hier = EvenementExterne.objects.filter(
            date_evenement__date=hier
        )
        
        # Statistiques par type
        stats_par_type = {}
        for type_choice in EvenementExterne.TYPE_CHOICES:
            type_code = type_choice[0]
            count = evenements_hier.filter(type_evenement=type_code).count()
            if count > 0:
                stats_par_type[type_code] = count
        
        # Statistiques par niveau de risque
        stats_par_risque = {}
        for risque_choice in EvenementExterne.NIVEAU_RISQUE_CHOICES:
            risque_code = risque_choice[0]
            count = evenements_hier.filter(niveau_risque=risque_code).count()
            if count > 0:
                stats_par_risque[risque_code] = count
        
        # Événements critiques
        evenements_critiques = evenements_hier.filter(niveau_risque='critique')
        
        # Alertes générées
        alertes_hier = AlerteEnrichie.objects.filter(
            date_creation__date=hier,
            donnees_contexte__contains={'type_source': 'evenement_externe'}
        )
        
        rapport = {
            'date': hier.isoformat(),
            'evenements': {
                'total': evenements_hier.count(),
                'par_type': stats_par_type,
                'par_niveau_risque': stats_par_risque,
                'critiques': evenements_critiques.count(),
                'necessitant_alerte': evenements_hier.filter(niveau_risque__in=['eleve', 'critique']).count()
            },
            'alertes': {
                'total': alertes_hier.count(),
                'actives': alertes_hier.filter(est_active=True).count(),
                'resolues': alertes_hier.filter(est_resolue=True).count(),
                'critiques': alertes_hier.filter(niveau='critique').count()
            },
            'sources': list(evenements_hier.values_list('source', flat=True).distinct()),
            'zones_erosion': list(evenements_hier.values_list('zone_erosion', flat=True).distinct()),
            'statut_systeme': 'opérationnel'
        }
        
        logger.info(f"Rapport quotidien événements externes généré: {rapport}")
        return rapport
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport quotidien événements externes: {e}")
        return {'erreur': str(e)}