#!/usr/bin/env python
"""
Service d'analyse simplifié pour les mesures des capteurs Arduino
Se déclenche automatiquement quand de nouvelles données arrivent
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from django.utils import timezone
from django.db import transaction

from .models import (
    CapteurArduino, MesureArduino, Zone, EvenementExterne,
    FusionDonnees, PredictionEnrichie, AlerteEnrichie, Prediction
)

logger = logging.getLogger(__name__)


class AnalyseCapteursService:
    """Service d'analyse simplifié pour les capteurs Arduino"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyser_mesures_capteurs(self, capteur_id: int = None) -> Dict:
        """
        Analyse les mesures des capteurs Arduino et génère des prédictions
        
        Args:
            capteur_id: ID du capteur spécifique (optionnel)
            
        Returns:
            Dict avec les résultats de l'analyse
        """
        try:
            self.logger.info("🔍 Début de l'analyse des mesures capteurs")
            
            # Récupérer les dernières mesures
            mesures_recentes = self._recuperer_mesures_recentes(capteur_id)
            
            if not mesures_recentes:
                return {"success": False, "message": "Aucune mesure récente trouvée"}
            
            # Analyser chaque zone
            resultats = []
            for zone, mesures in mesures_recentes.items():
                analyse = self._analyser_zone_mesures(zone, mesures)
                if analyse:
                    resultats.append(analyse)
            
            # Générer des alertes si nécessaire
            alertes_generees = self._generer_alertes_simples(resultats)
            
            self.logger.info(f"✅ Analyse terminée: {len(resultats)} zones analysées, {len(alertes_generees)} alertes générées")
            
            return {
                "success": True,
                "zones_analysees": len(resultats),
                "alertes_generees": len(alertes_generees),
                "resultats": resultats,
                "alertes": alertes_generees
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'analyse: {e}")
            return {"success": False, "message": f"Erreur: {str(e)}"}
    
    def _recuperer_mesures_recentes(self, capteur_id: int = None) -> Dict:
        """Récupère les mesures récentes des capteurs (dernières 2 heures)"""
        try:
            # Période de 2 heures
            depuis = timezone.now() - timedelta(hours=2)
            
            # Filtrer les capteurs
            if capteur_id:
                capteurs = CapteurArduino.objects.filter(id=capteur_id, actif=True)
            else:
                capteurs = CapteurArduino.objects.filter(actif=True)
            
            mesures_par_zone = {}
            
            for capteur in capteurs:
                zone = capteur.zone
                if zone not in mesures_par_zone:
                    mesures_par_zone[zone] = []
                
                # Récupérer les mesures récentes
                mesures = MesureArduino.objects.filter(
                    capteur=capteur,
                    timestamp__gte=depuis,
                    est_valide=True
                ).order_by('-timestamp')
                
                mesures_par_zone[zone].extend(mesures)
            
            return mesures_par_zone
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des mesures: {e}")
            return {}
    
    def _analyser_zone_mesures(self, zone: Zone, mesures: List[MesureArduino]) -> Optional[Dict]:
        """Analyse les mesures d'une zone spécifique"""
        try:
            if not mesures:
                return None
            
            # Calculer les statistiques des mesures
            stats_mesures = self._calculer_statistiques_mesures(mesures)
            
            # Calculer le score d'érosion basé sur les mesures
            score_erosion = self._calculer_score_erosion_mesures(stats_mesures)
            
            # Déterminer le niveau de risque
            niveau_risque = self._determiner_niveau_risque(score_erosion)
            
            # Générer une prédiction simple
            prediction = self._generer_prediction_simple(zone, stats_mesures, score_erosion, niveau_risque)
            
            return {
                "zone_id": zone.id,
                "zone_nom": zone.nom,
                "score_erosion": score_erosion,
                "niveau_risque": niveau_risque,
                "nb_mesures": len(mesures),
                "prediction_id": prediction.id if prediction else None,
                "stats_mesures": stats_mesures,
                "derniere_mesure": mesures[0].timestamp if mesures else None
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
    
    def _calculer_score_erosion_mesures(self, stats_mesures: Dict) -> float:
        """Calcule un score d'érosion basé uniquement sur les mesures des capteurs"""
        score = 0.0
        
        # Facteur température (si disponible)
        if '°C' in stats_mesures:
            temp = stats_mesures['°C']['moyenne']
            if temp > 30:  # Température élevée = risque accru
                score += (temp - 30) * 2
            elif temp < 15:  # Température basse = risque modéré
                score += (15 - temp) * 0.5
        
        # Facteur humidité (si disponible)
        if '%' in stats_mesures:
            hum = stats_mesures['%']['moyenne']
            if hum > 80:  # Humidité élevée = risque accru
                score += (hum - 80) * 0.5
            elif hum < 30:  # Humidité basse = risque modéré
                score += (30 - hum) * 0.2
        
        # Facteur pluie (si disponible)
        if 'pluie' in stats_mesures:
            pluie = stats_mesures['pluie']['moyenne']
            if pluie > 50:  # Pluie importante = risque accru
                score += (pluie - 50) * 0.3
        
        # Facteur niveau d'eau (si disponible)
        if 'eau' in stats_mesures:
            eau = stats_mesures['eau']['moyenne']
            if eau > 80:  # Niveau d'eau élevé = risque accru
                score += (eau - 80) * 0.4
        
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
    
    def _generer_prediction_simple(self, zone: Zone, stats_mesures: Dict, score_erosion: float, niveau_risque: str) -> Optional[Prediction]:
        """Génère une prédiction simple basée sur les mesures"""
        try:
            # Calculer la confiance basée sur le nombre de mesures
            nb_mesures_total = sum(stats['count'] for stats in stats_mesures.values())
            confiance_pourcentage = min(50 + (nb_mesures_total * 2), 95.0)
            
            # Calculer le taux d'érosion prédit
            taux_erosion_pred = score_erosion * 0.01  # Convertir en m/an
            
            # Créer une prédiction simple avec le modèle Prediction
            prediction = Prediction.objects.create(
                zone=zone,
                taux_erosion_pred_m_an=taux_erosion_pred,
                taux_erosion_min_m_an=max(0, taux_erosion_pred - taux_erosion_pred * 0.2),
                taux_erosion_max_m_an=taux_erosion_pred + taux_erosion_pred * 0.2,
                confiance_pourcentage=confiance_pourcentage,
                horizon_jours=7
            )
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de la prédiction: {e}")
            return None
    
    def _generer_recommandations_simples(self, niveau_risque: str, stats_mesures: Dict) -> List[str]:
        """Génère des recommandations basées sur le niveau de risque et les mesures"""
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
        
        # Recommandations spécifiques aux mesures
        if '°C' in stats_mesures:
            temp = stats_mesures['°C']['moyenne']
            if temp > 30:
                recommandations.append("🌡️ Température élevée - Surveiller l'impact sur l'érosion")
            elif temp < 15:
                recommandations.append("❄️ Température basse - Risque de gel")
        
        if '%' in stats_mesures:
            hum = stats_mesures['%']['moyenne']
            if hum > 80:
                recommandations.append("💧 Humidité élevée - Risque d'érosion hydrique")
            elif hum < 30:
                recommandations.append("🏜️ Humidité faible - Risque de sécheresse")
        
        if 'pluie' in stats_mesures:
            pluie = stats_mesures['pluie']['moyenne']
            if pluie > 50:
                recommandations.append("☔ Pluie importante - Surveillance renforcée")
        
        if 'eau' in stats_mesures:
            eau = stats_mesures['eau']['moyenne']
            if eau > 80:
                recommandations.append("🌊 Niveau d'eau élevé - Risque d'inondation")
        
        return recommandations
    
    def _generer_alertes_simples(self, resultats: List[Dict]) -> List[Dict]:
        """Génère des alertes simples si nécessaire"""
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
                        description=f"Risque d'érosion {resultat['niveau_risque']} détecté par les capteurs. Score: {resultat['score_erosion']:.1f}",
                        est_active=True,
                        actions_requises=[
                            "Surveillance renforcée des capteurs",
                            "Analyse des données en temps réel",
                            "Préparation des mesures de protection"
                        ],
                        donnees_contexte={
                            'score_erosion': resultat['score_erosion'],
                            'nb_mesures': resultat['nb_mesures'],
                            'stats_mesures': resultat['stats_mesures']
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
analyse_capteurs_service = AnalyseCapteursService()
