#!/usr/bin/env python
"""
Service d'analyse automatique des données capteurs Arduino
Se déclenche automatiquement quand de nouvelles données arrivent
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from django.utils import timezone
from django.db import transaction

from .models import (
    CapteurArduino, MesureArduino, Zone, EvenementExterne,
    FusionDonnees, PredictionEnrichie, AlerteEnrichie
)

logger = logging.getLogger(__name__)


class AnalyseAutomatiqueService:
    """Service d'analyse automatique des données capteurs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyser_nouvelles_donnees(self, capteur_id: int = None) -> Dict:
        """
        Analyse automatiquement les dernières données des capteurs
        
        Args:
            capteur_id: ID du capteur spécifique (optionnel)
            
        Returns:
            Dict avec les résultats de l'analyse
        """
        try:
            self.logger.info("🔍 Début de l'analyse automatique des données")
            
            # Récupérer les dernières données
            donnees_recentes = self._recuperer_donnees_recentes(capteur_id)
            
            if not donnees_recentes:
                return {"success": False, "message": "Aucune donnée récente trouvée"}
            
            # Analyser chaque zone
            resultats = []
            for zone, donnees in donnees_recentes.items():
                analyse = self._analyser_zone(zone, donnees)
                if analyse:
                    resultats.append(analyse)
            
            # Générer des alertes si nécessaire
            alertes_generees = self._generer_alertes_automatiques(resultats)
            
            self.logger.info(f"✅ Analyse terminée: {len(resultats)} zones analysées, {len(alertes_generees)} alertes générées")
            
            return {
                "success": True,
                "zones_analysees": len(resultats),
                "alertes_generees": len(alertes_generees),
                "resultats": resultats,
                "alertes": alertes_generees
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'analyse automatique: {e}")
            return {"success": False, "message": f"Erreur: {str(e)}"}
    
    def _recuperer_donnees_recentes(self, capteur_id: int = None) -> Dict:
        """Récupère les données récentes des capteurs (dernières 2 heures)"""
        try:
            # Période de 2 heures
            depuis = timezone.now() - timedelta(hours=2)
            
            # Filtrer les capteurs
            if capteur_id:
                capteurs = CapteurArduino.objects.filter(id=capteur_id, actif=True)
            else:
                capteurs = CapteurArduino.objects.filter(actif=True)
            
            donnees_par_zone = {}
            
            for capteur in capteurs:
                zone = capteur.zone
                if zone not in donnees_par_zone:
                    donnees_par_zone[zone] = {
                        'capteurs': [],
                        'mesures': [],
                        'evenements': []
                    }
                
                # Ajouter le capteur
                donnees_par_zone[zone]['capteurs'].append(capteur)
                
                # Récupérer les mesures récentes
                mesures = MesureArduino.objects.filter(
                    capteur=capteur,
                    timestamp__gte=depuis,
                    est_valide=True
                ).order_by('-timestamp')
                
                donnees_par_zone[zone]['mesures'].extend(mesures)
            
            # Récupérer les événements externes récents
            evenements = EvenementExterne.objects.filter(
                date_evenement__gte=depuis,
                is_valide=True
            ).order_by('-date_evenement')
            
            for evenement in evenements:
                if evenement.zone:
                    if evenement.zone not in donnees_par_zone:
                        donnees_par_zone[evenement.zone] = {
                            'capteurs': [],
                            'mesures': [],
                            'evenements': []
                        }
                    donnees_par_zone[evenement.zone]['evenements'].append(evenement)
            
            return donnees_par_zone
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des données: {e}")
            return {}
    
    def _analyser_zone(self, zone: Zone, donnees: Dict) -> Optional[Dict]:
        """Analyse les données d'une zone spécifique"""
        try:
            mesures = donnees['mesures']
            evenements = donnees['evenements']
            
            if not mesures and not evenements:
                return None
            
            # Calculer les statistiques des mesures
            stats_mesures = self._calculer_statistiques_mesures(mesures)
            
            # Analyser les événements
            stats_evenements = self._analyser_evenements(evenements)
            
            # Calculer le score d'érosion
            score_erosion = self._calculer_score_erosion(stats_mesures, stats_evenements)
            
            # Déterminer le niveau de risque
            niveau_risque = self._determiner_niveau_risque(score_erosion)
            
            # Créer une fusion de données
            fusion = self._creer_fusion_donnees(zone, stats_mesures, stats_evenements, score_erosion)
            
            # Générer une prédiction
            prediction = self._generer_prediction_automatique(fusion, niveau_risque)
            
            return {
                "zone_id": zone.id,
                "zone_nom": zone.nom,
                "score_erosion": score_erosion,
                "niveau_risque": niveau_risque,
                "nb_mesures": len(mesures),
                "nb_evenements": len(evenements),
                "fusion_id": fusion.id if fusion else None,
                "prediction_id": prediction.id if prediction else None,
                "stats_mesures": stats_mesures,
                "stats_evenements": stats_evenements
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de la zone {zone.nom}: {e}")
            return None
    
    def _calculer_statistiques_mesures(self, mesures: List[MesureArduino]) -> Dict:
        """Calcule les statistiques des mesures"""
        if not mesures:
            return {}
        
        # Grouper par type de mesure
        mesures_par_type = {}
        for mesure in mesures:
            unite = mesure.unite
            if unite not in mesures_par_type:
                mesures_par_type[unite] = []
            mesures_par_type[unite].append(mesure.valeur)
        
        stats = {}
        for unite, valeurs in mesures_par_type.items():
            if valeurs:
                stats[unite] = {
                    'moyenne': sum(valeurs) / len(valeurs),
                    'min': min(valeurs),
                    'max': max(valeurs),
                    'count': len(valeurs),
                    'derniere_valeur': valeurs[0]  # Première = plus récente (trié par -timestamp)
                }
        
        return stats
    
    def _analyser_evenements(self, evenements: List[EvenementExterne]) -> Dict:
        """Analyse les événements externes"""
        if not evenements:
            return {}
        
        # Compter par type d'événement
        types_evenements = {}
        for event in evenements:
            type_event = event.type_evenement
            if type_event not in types_evenements:
                types_evenements[type_event] = {
                    'count': 0,
                    'intensite_moyenne': 0,
                    'niveau_risque_max': 'faible'
                }
            
            types_evenements[type_event]['count'] += 1
            types_evenements[type_event]['intensite_moyenne'] += event.intensite
            
            # Déterminer le niveau de risque max
            if event.niveau_risque == 'critique':
                types_evenements[type_event]['niveau_risque_max'] = 'critique'
            elif event.niveau_risque == 'eleve' and types_evenements[type_event]['niveau_risque_max'] != 'critique':
                types_evenements[type_event]['niveau_risque_max'] = 'eleve'
            elif event.niveau_risque == 'modere' and types_evenements[type_event]['niveau_risque_max'] not in ['critique', 'eleve']:
                types_evenements[type_event]['niveau_risque_max'] = 'modere'
        
        # Calculer les moyennes
        for type_event in types_evenements:
            count = types_evenements[type_event]['count']
            types_evenements[type_event]['intensite_moyenne'] /= count
        
        return types_evenements
    
    def _calculer_score_erosion(self, stats_mesures: Dict, stats_evenements: Dict) -> float:
        """Calcule un score d'érosion basé sur les données"""
        score = 0.0
        
        # Facteur température (si disponible)
        if '°C' in stats_mesures:
            temp = stats_mesures['°C']['moyenne']
            if temp > 30:  # Température élevée = risque accru
                score += (temp - 30) * 2
        
        # Facteur humidité (si disponible)
        if '%' in stats_mesures:
            hum = stats_mesures['%']['moyenne']
            if hum > 80:  # Humidité élevée = risque accru
                score += (hum - 80) * 0.5
        
        # Facteur événements
        for type_event, stats in stats_evenements.items():
            intensite = stats['intensite_moyenne']
            count = stats['count']
            
            # Pondération selon le type d'événement
            if type_event in ['tempete', 'ouragan', 'cyclone']:
                score += intensite * count * 3
            elif type_event in ['vent_fort', 'houle']:
                score += intensite * count * 2
            elif type_event == 'pluie':
                score += intensite * count * 1.5
            else:
                score += intensite * count * 1
        
        return min(score, 100.0)  # Limiter à 100
    
    def _determiner_niveau_risque(self, score_erosion: float) -> str:
        """Détermine le niveau de risque basé sur le score"""
        if score_erosion >= 80:
            return 'critique'
        elif score_erosion >= 60:
            return 'eleve'
        elif score_erosion >= 30:
            return 'modere'
        else:
            return 'faible'
    
    def _creer_fusion_donnees(self, zone: Zone, stats_mesures: Dict, stats_evenements: Dict, score_erosion: float) -> Optional[FusionDonnees]:
        """Crée une fusion de données pour la zone"""
        try:
            # Calculer la probabilité d'érosion
            probabilite_erosion = min(score_erosion / 100.0, 1.0)
            
            # Identifier les facteurs dominants
            facteurs_dominants = []
            if '°C' in stats_mesures and stats_mesures['°C']['moyenne'] > 30:
                facteurs_dominants.append('temperature_elevee')
            if '%' in stats_mesures and stats_mesures['%']['moyenne'] > 80:
                facteurs_dominants.append('humidite_elevee')
            
            for type_event in stats_evenements:
                if stats_evenements[type_event]['count'] > 0:
                    facteurs_dominants.append(f'evenement_{type_event}')
            
            # Déterminer le niveau de risque
            niveau_risque = self._determiner_niveau_risque(score_erosion)
            
            # Créer un événement virtuel pour l'analyse automatique
            evenement_virtuel, _ = EvenementExterne.objects.get_or_create(
                type_evenement='autre',  # Utiliser 'autre' au lieu de 'analyse_automatique'
                zone=zone,
                date_evenement=timezone.now(),
                defaults={
                    'intensite': score_erosion / 10,  # Intensité basée sur le score
                    'niveau_risque': niveau_risque,
                    'duree': '2h',  # Durée par défaut
                    'statut': 'recu',
                    'source': 'api',
                    'is_valide': True,
                    'is_traite': True
                }
            )
            
            # Créer la fusion
            fusion = FusionDonnees.objects.create(
                zone=zone,
                evenement_externe=evenement_virtuel,
                periode_debut=timezone.now() - timedelta(hours=2),
                periode_fin=timezone.now(),
                mesures_arduino_count=sum(len(valeurs) for valeurs in stats_mesures.values() if isinstance(valeurs, dict) and 'count' in valeurs),
                evenements_externes_count=sum(stats['count'] for stats in stats_evenements.values()),
                score_erosion=score_erosion,
                probabilite_erosion=probabilite_erosion,
                facteurs_dominants=facteurs_dominants,
                statut='terminee',
                date_fin=timezone.now(),
                commentaires=f"Analyse automatique - Score: {score_erosion:.1f}"
            )
            
            return fusion
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la création de la fusion: {e}")
            return None
    
    def _generer_prediction_automatique(self, fusion: FusionDonnees, niveau_risque: str) -> Optional[PredictionEnrichie]:
        """Génère une prédiction automatique basée sur la fusion"""
        try:
            # Déterminer si érosion prédite
            erosion_predite = fusion.probabilite_erosion > 0.5
            
            # Calculer la confiance
            confiance_pourcentage = min(fusion.score_erosion, 95.0)
            
            # Calculer le taux d'érosion prédit
            taux_erosion_pred = fusion.score_erosion * 0.01  # Convertir en m/an
            
            # Générer des recommandations
            recommandations = self._generer_recommandations(niveau_risque, fusion.facteurs_dominants)
            
            # Créer la prédiction
            prediction = PredictionEnrichie.objects.create(
                zone=fusion.zone,
                fusion_donnees=fusion,
                erosion_predite=erosion_predite,
                niveau_erosion=niveau_risque,
                confiance_pourcentage=confiance_pourcentage,
                horizon_jours=7,
                taux_erosion_pred_m_an=taux_erosion_pred,
                facteur_evenements=fusion.score_erosion * 0.4,
                facteur_mesures_arduino=fusion.score_erosion * 0.3,
                facteur_historique=fusion.score_erosion * 0.1,
                recommandations=recommandations,
                actions_urgentes=[],
                modele_utilise="Modèle automatique multi-facteurs",
                parametres_modele={
                    'score_erosion': fusion.score_erosion,
                    'probabilite_erosion': fusion.probabilite_erosion,
                    'facteurs_dominants': fusion.facteurs_dominants
                },
                commentaires=f"Prédiction générée automatiquement - Score: {fusion.score_erosion:.1f}"
            )
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de la prédiction: {e}")
            return None
    
    def _generer_recommandations(self, niveau_risque: str, facteurs_dominants: List[str]) -> List[str]:
        """Génère des recommandations basées sur le niveau de risque et les facteurs"""
        recommandations = []
        
        if niveau_risque == 'critique':
            recommandations.extend([
                "🚨 ALERTE CRITIQUE - Surveillance renforcée requise",
                "📞 Contacter les autorités locales immédiatement",
                "🚧 Mettre en place des mesures de protection d'urgence"
            ])
        elif niveau_risque == 'eleve':
            recommandations.extend([
                "⚠️ Risque élevé détecté - Surveillance accrue",
                "📊 Analyser les tendances des dernières heures",
                "🛡️ Préparer des mesures de protection"
            ])
        elif niveau_risque == 'modere':
            recommandations.extend([
                "📈 Risque modéré - Continuer la surveillance",
                "📋 Documenter les conditions actuelles",
                "🔍 Surveiller l'évolution des paramètres"
            ])
        else:
            recommandations.extend([
                "✅ Conditions normales - Surveillance de routine",
                "📊 Maintenir la collecte de données",
                "🔄 Continuer le monitoring régulier"
            ])
        
        # Recommandations spécifiques aux facteurs
        if 'temperature_elevee' in facteurs_dominants:
            recommandations.append("🌡️ Température élevée - Surveiller l'impact sur l'érosion")
        
        if 'humidite_elevee' in facteurs_dominants:
            recommandations.append("💧 Humidité élevée - Risque d'érosion hydrique")
        
        if any('evenement_' in f for f in facteurs_dominants):
            recommandations.append("🌪️ Événements météo détectés - Surveillance renforcée")
        
        return recommandations
    
    def _generer_alertes_automatiques(self, resultats: List[Dict]) -> List[Dict]:
        """Génère des alertes automatiques si nécessaire"""
        alertes_generees = []
        
        for resultat in resultats:
            if resultat['niveau_risque'] in ['eleve', 'critique']:
                try:
                    zone = Zone.objects.get(id=resultat['zone_id'])
                    
                    # Créer une alerte enrichie
                    alerte = AlerteEnrichie.objects.create(
                        zone=zone,
                        prediction_enrichie_id=resultat.get('prediction_id'),
                        type='erosion_predite',
                        niveau=resultat['niveau_risque'],
                        titre=f"🚨 Alerte érosion - {zone.nom}",
                        description=f"Risque d'érosion {resultat['niveau_risque']} détecté. Score: {resultat['score_erosion']:.1f}",
                        est_active=True,
                        actions_requises=[
                            "Surveillance renforcée",
                            "Analyse des données en temps réel",
                            "Préparation des mesures de protection"
                        ],
                        donnees_contexte={
                            'score_erosion': resultat['score_erosion'],
                            'nb_mesures': resultat['nb_mesures'],
                            'nb_evenements': resultat['nb_evenements'],
                            'facteurs_dominants': resultat['stats_evenements']
                        }
                    )
                    
                    alertes_generees.append({
                        'alerte_id': alerte.id,
                        'zone': zone.nom,
                        'niveau': resultat['niveau_risque'],
                        'titre': alerte.titre
                    })
                    
                except Exception as e:
                    self.logger.error(f"Erreur lors de la création de l'alerte: {e}")
        
        return alertes_generees


# Instance globale du service
analyse_service = AnalyseAutomatiqueService()
