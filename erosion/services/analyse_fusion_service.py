"""
Service de fusion et analyse des événements externes avec les mesures Arduino
Version simplifiée sans dépendances sklearn
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from django.db.models import Q, Avg, Max, Min, Count
import json

from ..models import (
    EvenementExterne, MesureArduino, Zone, FusionDonnees, 
    PredictionEnrichie, AlerteEnrichie, HistoriqueErosion
)

logger = logging.getLogger(__name__)


class AnalyseFusionService:
    """Service principal pour l'analyse de fusion des données"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.is_trained = False
    
    def analyser_evenement(self, evenement_id: int) -> Dict:
        """
        Analyser un événement externe spécifique et créer une fusion de données
        """
        try:
            evenement = EvenementExterne.objects.get(id=evenement_id)
            zone = evenement.zone
            
            logger.info(f"Analyse de l'événement {evenement_id}: {evenement.type_evenement}")
            
            # Définir la période d'analyse (7 jours avant et après l'événement)
            periode_debut = evenement.date_evenement - timedelta(days=7)
            periode_fin = evenement.date_evenement + timedelta(days=7)
            
            # Récupérer les données de la zone
            mesures_arduino = self._recuperer_mesures_arduino(zone, periode_debut, periode_fin)
            evenements_contexte = self._recuperer_evenements_contexte(zone, periode_debut, periode_fin)
            historique_erosion = self._recuperer_historique_erosion(zone)
            
            # Créer la fusion de données
            fusion = self._creer_fusion_donnees(
                evenement, zone, periode_debut, periode_fin,
                mesures_arduino, evenements_contexte, historique_erosion
            )
            
            # Analyser et prédire
            prediction = self._generer_prediction(fusion)
            
            # Créer des alertes si nécessaire
            alertes = self._creer_alertes(fusion, prediction)
            
            return {
                'success': True,
                'fusion_id': fusion.id,
                'prediction_id': prediction.id if prediction else None,
                'alertes_crees': len(alertes),
                'message': 'Analyse terminée avec succès'
            }
            
        except EvenementExterne.DoesNotExist:
            logger.error(f"Événement {evenement_id} introuvable")
            return {'success': False, 'message': 'Événement introuvable'}
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de l'événement {evenement_id}: {e}")
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def analyser_zone(self, zone_id: int, periode_jours: int = 30) -> Dict:
        """
        Analyser une zone complète pour créer des fusions de données
        """
        try:
            zone = Zone.objects.get(id=zone_id)
            
            # Définir la période d'analyse
            periode_fin = timezone.now()
            periode_debut = periode_fin - timedelta(days=periode_jours)
            
            logger.info(f"Analyse de la zone {zone.nom} sur {periode_jours} jours")
            
            # Récupérer tous les événements de la période
            evenements = EvenementExterne.objects.filter(
                zone=zone,
                date_evenement__gte=periode_debut,
                date_evenement__lte=periode_fin,
                is_valide=True
            ).order_by('date_evenement')
            
            fusions_creees = []
            predictions_creees = []
            alertes_creees = []
            
            for evenement in evenements:
                # Analyser chaque événement
                resultat = self.analyser_evenement(evenement.id)
                
                if resultat['success']:
                    fusions_creees.append(resultat['fusion_id'])
                    if resultat['prediction_id']:
                        predictions_creees.append(resultat['prediction_id'])
                    alertes_creees.extend(resultat.get('alertes_crees', []))
            
            return {
                'success': True,
                'zone_id': zone_id,
                'zone_nom': zone.nom,
                'periode_jours': periode_jours,
                'evenements_analyses': evenements.count(),
                'fusions_creees': len(fusions_creees),
                'predictions_creees': len(predictions_creees),
                'alertes_creees': len(alertes_creees),
                'message': f'Analyse de la zone {zone.nom} terminée'
            }
            
        except Zone.DoesNotExist:
            logger.error(f"Zone {zone_id} introuvable")
            return {'success': False, 'message': 'Zone introuvable'}
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de la zone {zone_id}: {e}")
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def _recuperer_mesures_arduino(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """
        Récupérer les mesures Arduino de la zone pour la période donnée
        """
        mesures = MesureArduino.objects.filter(
            capteur__zone=zone,
            timestamp__gte=periode_debut,
            timestamp__lte=periode_fin,
            est_valide=True
        ).select_related('capteur').order_by('timestamp')
        
        # Grouper par capteur et calculer des statistiques
        mesures_par_capteur = {}
        for mesure in mesures:
            capteur_id = mesure.capteur.id
            if capteur_id not in mesures_par_capteur:
                mesures_par_capteur[capteur_id] = {
                    'capteur_id': capteur_id,
                    'capteur_nom': mesure.capteur.nom,
                    'capteur_type': mesure.capteur.type_capteur,
                    'valeurs': [],
                    'timestamps': []
                }
            
            mesures_par_capteur[capteur_id]['valeurs'].append(mesure.valeur)
            mesures_par_capteur[capteur_id]['timestamps'].append(mesure.timestamp)
        
        # Calculer les statistiques pour chaque capteur
        mesures_analysees = []
        for capteur_data in mesures_par_capteur.values():
            if capteur_data['valeurs']:
                mesures_analysees.append({
                    'capteur_id': capteur_data['capteur_id'],
                    'capteur_nom': capteur_data['capteur_nom'],
                    'capteur_type': capteur_data['capteur_type'],
                    'nombre_mesures': len(capteur_data['valeurs']),
                    'valeur_moyenne': np.mean(capteur_data['valeurs']),
                    'valeur_min': np.min(capteur_data['valeurs']),
                    'valeur_max': np.max(capteur_data['valeurs']),
                    'valeur_std': np.std(capteur_data['valeurs']),
                    'periode_debut': min(capteur_data['timestamps']),
                    'periode_fin': max(capteur_data['timestamps'])
                })
        
        logger.info(f"Récupéré {len(mesures_analysees)} capteurs avec mesures pour la zone {zone.nom}")
        return mesures_analysees
    
    def _recuperer_evenements_contexte(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """
        Récupérer les événements externes de contexte pour la zone
        """
        evenements = EvenementExterne.objects.filter(
            zone=zone,
            date_evenement__gte=periode_debut,
            date_evenement__lte=periode_fin,
            is_valide=True
        ).order_by('date_evenement')
        
        evenements_analysees = []
        for evenement in evenements:
            evenements_analysees.append({
                'id': evenement.id,
                'type_evenement': evenement.type_evenement,
                'intensite': evenement.intensite,
                'intensite_categorie': evenement.intensite_categorie,
                'date_evenement': evenement.date_evenement,
                'source': evenement.source,
                'duree_minutes': evenement.duree_minutes,
                'rayon_impact_km': evenement.rayon_impact_km,
                'niveau_risque': evenement.niveau_risque
            })
        
        logger.info(f"Récupéré {len(evenements_analysees)} événements de contexte pour la zone {zone.nom}")
        return evenements_analysees
    
    def _recuperer_historique_erosion(self, zone: Zone) -> List[Dict]:
        """
        Récupérer l'historique d'érosion de la zone
        """
        historique = HistoriqueErosion.objects.filter(
            zone=zone
        ).order_by('-date_mesure')[:12]  # Derniers 12 mois
        
        historique_analyse = []
        for h in historique:
            historique_analyse.append({
                'date_mesure': h.date_mesure,
                'taux_erosion_m_an': h.taux_erosion_m_an,
                'methode_mesure': h.methode_mesure,
                'precision_m': h.precision_m
            })
        
        logger.info(f"Récupéré {len(historique_analyse)} mesures d'historique pour la zone {zone.nom}")
        return historique_analyse
    
    def _creer_fusion_donnees(self, evenement: EvenementExterne, zone: Zone, 
                            periode_debut: datetime, periode_fin: datetime,
                            mesures_arduino: List[Dict], evenements_contexte: List[Dict],
                            historique_erosion: List[Dict]) -> FusionDonnees:
        """
        Créer une fusion de données à partir des informations collectées
        """
        # Calculer le score d'érosion basé sur les données
        score_erosion = self._calculer_score_erosion(
            evenement, mesures_arduino, evenements_contexte, historique_erosion
        )
        
        # Calculer la probabilité d'érosion
        probabilite_erosion = self._calculer_probabilite_erosion(score_erosion)
        
        # Identifier les facteurs dominants
        facteurs_dominants = self._identifier_facteurs_dominants(
            evenement, mesures_arduino, evenements_contexte
        )
        
        # Créer la fusion
        fusion = FusionDonnees.objects.create(
            zone=zone,
            evenement_externe=evenement,
            periode_debut=periode_debut,
            periode_fin=periode_fin,
            mesures_arduino_count=len(mesures_arduino),
            evenements_externes_count=len(evenements_contexte),
            score_erosion=score_erosion,
            probabilite_erosion=probabilite_erosion,
            facteurs_dominants=facteurs_dominants,
            statut='terminee',
            date_fin=timezone.now(),
            commentaires=f"Fusion créée automatiquement pour l'événement {evenement.type_evenement}"
        )
        
        logger.info(f"Fusion créée: {fusion.id} avec score {score_erosion:.2f}")
        return fusion
    
    def _calculer_score_erosion(self, evenement: EvenementExterne, mesures_arduino: List[Dict],
                              evenements_contexte: List[Dict], historique_erosion: List[Dict]) -> float:
        """
        Calculer un score d'érosion basé sur tous les facteurs
        """
        score = 0.0
        
        # Facteur événement principal (40% du score)
        score_evenement = self._calculer_score_evenement(evenement)
        score += score_evenement * 0.4
        
        # Facteur mesures Arduino (30% du score)
        score_mesures = self._calculer_score_mesures(mesures_arduino)
        score += score_mesures * 0.3
        
        # Facteur événements de contexte (20% du score)
        score_contexte = self._calculer_score_contexte(evenements_contexte)
        score += score_contexte * 0.2
        
        # Facteur historique (10% du score)
        score_historique = self._calculer_score_historique(historique_erosion)
        score += score_historique * 0.1
        
        # Normaliser entre 0 et 100
        score = max(0, min(100, score))
        
        logger.debug(f"Scores: événement={score_evenement:.2f}, mesures={score_mesures:.2f}, "
                    f"contexte={score_contexte:.2f}, historique={score_historique:.2f}, total={score:.2f}")
        
        return score
    
    def _calculer_score_evenement(self, evenement: EvenementExterne) -> float:
        """
        Calculer le score basé sur l'événement principal
        """
        score = evenement.intensite
        
        # Modificateurs selon le type d'événement
        modificateurs = {
            'tempete': 1.2,
            'ouragan': 1.5,
            'cyclone': 1.5,
            'tsunami': 2.0,
            'vague': 1.1,
            'vent_fort': 1.0,
            'pluie': 0.8,
            'maree_exceptionnelle': 1.3,
            'secheresse': 0.6,
            'inondation': 1.1,
            'autre': 1.0
        }
        
        modificateur = modificateurs.get(evenement.type_evenement, 1.0)
        score *= modificateur
        
        # Bonus pour durée et rayon d'impact
        if evenement.duree_minutes:
            score += min(evenement.duree_minutes / 60, 10)  # Max 10 points pour durée
        
        if evenement.rayon_impact_km:
            score += min(evenement.rayon_impact_km, 15)  # Max 15 points pour rayon
        
        return min(score, 100)
    
    def _calculer_score_mesures(self, mesures_arduino: List[Dict]) -> float:
        """
        Calculer le score basé sur les mesures Arduino
        """
        if not mesures_arduino:
            return 50.0  # Score neutre si pas de mesures
        
        score_total = 0.0
        poids_total = 0.0
        
        for mesure in mesures_arduino:
            # Poids selon le type de capteur
            poids_capteur = {
                'temperature': 0.8,
                'humidite': 0.6,
                'pression': 0.7,
                'vent_vitesse': 1.2,
                'vent_direction': 0.9,
                'pluviometrie': 1.1,
                'niveau_mer': 1.5,
                'salinite': 1.0,
                'ph': 0.8,
                'turbidite': 1.0,
                'gps': 0.5,
                'accelerometre': 0.7,
                'gyroscope': 0.6
            }
            
            poids = poids_capteur.get(mesure['capteur_type'], 1.0)
            
            # Score basé sur les valeurs anormales
            if mesure['capteur_type'] == 'vent_vitesse':
                # Vent fort = risque élevé
                score_capteur = min(mesure['valeur_max'] * 2, 100)
            elif mesure['capteur_type'] == 'niveau_mer':
                # Niveau de mer élevé = risque élevé
                score_capteur = min(mesure['valeur_max'] * 20, 100)
            elif mesure['capteur_type'] == 'pluviometrie':
                # Pluie intense = risque élevé
                score_capteur = min(mesure['valeur_max'] * 0.5, 100)
            else:
                # Score basé sur la variabilité
                score_capteur = min(mesure['valeur_std'] * 10, 100)
            
            score_total += score_capteur * poids
            poids_total += poids
        
        return score_total / poids_total if poids_total > 0 else 50.0
    
    def _calculer_score_contexte(self, evenements_contexte: List[Dict]) -> float:
        """
        Calculer le score basé sur les événements de contexte
        """
        if not evenements_contexte:
            return 50.0
        
        # Compter les événements par intensité
        evenements_forts = sum(1 for e in evenements_contexte if e['intensite'] > 70)
        evenements_moderes = sum(1 for e in evenements_contexte if 40 <= e['intensite'] <= 70)
        evenements_faibles = sum(1 for e in evenements_contexte if e['intensite'] < 40)
        
        # Score basé sur la fréquence et l'intensité
        score = (evenements_forts * 20 + evenements_moderes * 10 + evenements_faibles * 5)
        score = min(score, 100)
        
        return score
    
    def _calculer_score_historique(self, historique_erosion: List[Dict]) -> float:
        """
        Calculer le score basé sur l'historique d'érosion
        """
        if not historique_erosion:
            return 50.0
        
        # Moyenne des taux d'érosion récents
        taux_moyen = np.mean([h['taux_erosion_m_an'] for h in historique_erosion])
        
        # Score basé sur le taux d'érosion historique
        if taux_moyen > 2.0:  # Plus de 2m/an
            return 80.0
        elif taux_moyen > 1.0:  # Plus de 1m/an
            return 60.0
        elif taux_moyen > 0.5:  # Plus de 0.5m/an
            return 40.0
        else:
            return 20.0
    
    def _calculer_probabilite_erosion(self, score_erosion: float) -> float:
        """
        Convertir le score d'érosion en probabilité (0-1)
        """
        # Fonction sigmoïde pour convertir le score en probabilité
        import math
        x = (score_erosion - 50) / 20  # Normaliser autour de 50
        probabilite = 1 / (1 + math.exp(-x))
        return probabilite
    
    def _identifier_facteurs_dominants(self, evenement: EvenementExterne, 
                                     mesures_arduino: List[Dict], 
                                     evenements_contexte: List[Dict]) -> List[str]:
        """
        Identifier les facteurs dominants dans l'analyse
        """
        facteurs = []
        
        # Facteur événement principal
        if evenement.intensite > 80:
            facteurs.append(f"Événement {evenement.type_evenement} extrême")
        elif evenement.intensite > 60:
            facteurs.append(f"Événement {evenement.type_evenement} fort")
        
        # Facteurs mesures Arduino
        for mesure in mesures_arduino:
            if mesure['capteur_type'] == 'vent_vitesse' and mesure['valeur_max'] > 50:
                facteurs.append("Vent très fort détecté")
            elif mesure['capteur_type'] == 'niveau_mer' and mesure['valeur_max'] > 2:
                facteurs.append("Niveau de mer élevé")
            elif mesure['capteur_type'] == 'pluviometrie' and mesure['valeur_max'] > 50:
                facteurs.append("Précipitations intenses")
        
        # Facteurs contexte
        if len(evenements_contexte) > 5:
            facteurs.append("Multiples événements climatiques")
        
        return facteurs[:5]  # Limiter à 5 facteurs principaux
    
    def _generer_prediction(self, fusion: FusionDonnees) -> Optional[PredictionEnrichie]:
        """
        Générer une prédiction d'érosion basée sur la fusion de données
        """
        try:
            # Déterminer si l'érosion est prédite
            erosion_predite = fusion.probabilite_erosion > 0.6
            
            # Déterminer le niveau d'érosion
            if fusion.score_erosion > 80:
                niveau_erosion = 'critique'
            elif fusion.score_erosion > 60:
                niveau_erosion = 'eleve'
            elif fusion.score_erosion > 40:
                niveau_erosion = 'modere'
            else:
                niveau_erosion = 'faible'
            
            # Calculer la confiance
            confiance_pourcentage = min(fusion.probabilite_erosion * 100, 95)
            
            # Calculer le taux d'érosion prédit
            taux_erosion_pred = fusion.score_erosion / 100 * 3.0  # Max 3m/an
            
            # Générer les recommandations
            recommandations = self._generer_recommandations(fusion, erosion_predite, niveau_erosion)
            
            # Générer les actions urgentes
            actions_urgentes = self._generer_actions_urgentes(fusion, niveau_erosion)
            
            # Créer la prédiction
            prediction = PredictionEnrichie.objects.create(
                zone=fusion.zone,
                fusion_donnees=fusion,
                erosion_predite=erosion_predite,
                niveau_erosion=niveau_erosion,
                confiance_pourcentage=confiance_pourcentage,
                horizon_jours=7,  # Prédiction sur 7 jours
                taux_erosion_pred_m_an=taux_erosion_pred,
                facteur_evenements=fusion.score_erosion * 0.4,
                facteur_mesures_arduino=fusion.score_erosion * 0.3,
                facteur_historique=fusion.score_erosion * 0.1,
                recommandations=recommandations,
                actions_urgentes=actions_urgentes,
                modele_utilise="Modèle enrichi multi-facteurs v1.0",
                parametres_modele={
                    'score_erosion': fusion.score_erosion,
                    'probabilite_erosion': fusion.probabilite_erosion,
                    'facteurs_dominants': fusion.facteurs_dominants
                },
                commentaires=f"Prédiction générée automatiquement pour l'événement {fusion.evenement_externe.type_evenement}"
            )
            
            logger.info(f"Prédiction créée: {prediction.id} - Érosion: {erosion_predite} ({confiance_pourcentage:.1f}%)")
            return prediction
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de la prédiction: {e}")
            return None
    
    def _generer_recommandations(self, fusion: FusionDonnees, erosion_predite: bool, niveau_erosion: str) -> List[str]:
        """
        Générer des recommandations basées sur l'analyse
        """
        recommandations = []
        
        if erosion_predite:
            if niveau_erosion == 'critique':
                recommandations.extend([
                    "Évacuation immédiate recommandée",
                    "Surveillance 24h/24 nécessaire",
                    "Préparation des équipements d'urgence"
                ])
            elif niveau_erosion == 'eleve':
                recommandations.extend([
                    "Surveillance renforcée recommandée",
                    "Préparation des mesures de protection",
                    "Communication avec les autorités locales"
                ])
            else:
                recommandations.extend([
                    "Surveillance normale maintenue",
                    "Vérification des équipements de mesure"
                ])
        else:
            recommandations.append("Aucune action urgente requise")
        
        # Recommandations spécifiques selon les facteurs dominants
        for facteur in fusion.facteurs_dominants:
            if "vent" in facteur.lower():
                recommandations.append("Vérifier la résistance des structures au vent")
            elif "mer" in facteur.lower():
                recommandations.append("Surveiller les niveaux de marée")
            elif "pluie" in facteur.lower():
                recommandations.append("Vérifier les systèmes de drainage")
        
        return recommandations
    
    def _generer_actions_urgentes(self, fusion: FusionDonnees, niveau_erosion: str) -> List[str]:
        """
        Générer des actions urgentes basées sur le niveau d'érosion
        """
        actions = []
        
        if niveau_erosion == 'critique':
            actions.extend([
                "Alerter les services d'urgence",
                "Évacuation immédiate de la zone",
                "Fermeture des accès à la zone",
                "Mise en place de barrières de protection"
            ])
        elif niveau_erosion == 'eleve':
            actions.extend([
                "Préparer les équipements d'évacuation",
                "Informer la population locale",
                "Renforcer la surveillance"
            ])
        elif niveau_erosion == 'modere':
            actions.extend([
                "Surveillance renforcée",
                "Préparation des mesures préventives"
            ])
        
        return actions
    
    def _creer_alertes(self, fusion: FusionDonnees, prediction: Optional[PredictionEnrichie]) -> List[AlerteEnrichie]:
        """
        Créer des alertes basées sur la fusion et la prédiction
        """
        alertes = []
        
        try:
            # Alerte pour événement extrême
            if fusion.evenement_externe.intensite > 90:
                alerte = AlerteEnrichie.objects.create(
                    zone=fusion.zone,
                    evenement_externe=fusion.evenement_externe,
                    type='evenement_extreme',
                    niveau='critique',
                    titre=f"Événement {fusion.evenement_externe.type_evenement} extrême détecté",
                    description=f"Intensité de {fusion.evenement_externe.intensite}% - Surveillance maximale requise",
                    actions_requises=[
                        "Surveillance 24h/24",
                        "Préparation évacuation",
                        "Alerte autorités"
                    ],
                    donnees_contexte={
                        'score_erosion': fusion.score_erosion,
                        'probabilite_erosion': fusion.probabilite_erosion,
                        'facteurs_dominants': fusion.facteurs_dominants
                    }
                )
                alertes.append(alerte)
            
            # Alerte pour prédiction d'érosion
            if prediction and prediction.erosion_predite and prediction.niveau_erosion in ['eleve', 'critique']:
                alerte = AlerteEnrichie.objects.create(
                    zone=fusion.zone,
                    prediction_enrichie=prediction,
                    type='erosion_predite',
                    niveau='alerte' if prediction.niveau_erosion == 'eleve' else 'critique',
                    titre=f"Érosion prédite - Niveau {prediction.niveau_erosion}",
                    description=f"Probabilité d'érosion: {prediction.confiance_pourcentage:.1f}% - Horizon: {prediction.horizon_jours} jours",
                    actions_requises=prediction.actions_urgentes,
                    donnees_contexte={
                        'confiance_prediction': prediction.confiance_pourcentage,
                        'taux_erosion_pred': prediction.taux_erosion_pred_m_an,
                        'recommandations': prediction.recommandations
                    }
                )
                alertes.append(alerte)
            
            logger.info(f"Créé {len(alertes)} alertes pour la fusion {fusion.id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la création des alertes: {e}")
        
        return alertes


class ArchiveService:
    """Service pour l'archivage des données"""
    
    def creer_archive(self, type_donnees: str, zone_id: int, periode_jours: int) -> Dict:
        """
        Créer une archive de données pour l'IA
        """
        try:
            zone = Zone.objects.get(id=zone_id)
            periode_fin = timezone.now()
            periode_debut = periode_fin - timedelta(days=periode_jours)
            
            # Récupérer les données selon le type
            if type_donnees == 'mesures_arduino':
                donnees = self._archiver_mesures_arduino(zone, periode_debut, periode_fin)
            elif type_donnees == 'evenements_externes':
                donnees = self._archiver_evenements_externes(zone, periode_debut, periode_fin)
            elif type_donnees == 'fusions':
                donnees = self._archiver_fusions(zone, periode_debut, periode_fin)
            elif type_donnees == 'predictions':
                donnees = self._archiver_predictions(zone, periode_debut, periode_fin)
            elif type_donnees == 'alertes':
                donnees = self._archiver_alertes(zone, periode_debut, periode_fin)
            else:
                return {'success': False, 'message': 'Type de données non supporté'}
            
            # Sauvegarder l'archive
            chemin_fichier = f"archives/{type_donnees}_{zone_id}_{periode_debut.strftime('%Y%m%d')}.json"
            
            import os
            os.makedirs(os.path.dirname(chemin_fichier), exist_ok=True)
            
            with open(chemin_fichier, 'w', encoding='utf-8') as f:
                json.dump(donnees, f, ensure_ascii=False, indent=2, default=str)
            
            # Créer l'enregistrement d'archive
            taille_fichier = os.path.getsize(chemin_fichier) / (1024 * 1024)  # MB
            
            archive = ArchiveDonnees.objects.create(
                type_donnees=type_donnees,
                zone=zone,
                periode_debut=periode_debut,
                periode_fin=periode_fin,
                nombre_elements=len(donnees),
                taille_fichier_mb=taille_fichier,
                chemin_fichier=chemin_fichier,
                description=f"Archive automatique {type_donnees} pour {zone.nom}"
            )
            
            return {
                'success': True,
                'archive_id': archive.id,
                'nombre_elements': len(donnees),
                'taille_fichier_mb': taille_fichier,
                'chemin_fichier': chemin_fichier
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'archive: {e}")
            return {'success': False, 'message': f'Erreur: {str(e)}'}
    
    def _archiver_mesures_arduino(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """Archiver les mesures Arduino"""
        mesures = MesureArduino.objects.filter(
            capteur__zone=zone,
            timestamp__gte=periode_debut,
            timestamp__lte=periode_fin
        ).select_related('capteur')
        
        return [
            {
                'id': m.id,
                'capteur_id': m.capteur.id,
                'capteur_nom': m.capteur.nom,
                'capteur_type': m.capteur.type_capteur,
                'valeur': m.valeur,
                'unite': m.unite,
                'timestamp': m.timestamp,
                'qualite_donnee': m.qualite_donnee,
                'source_donnee': m.source_donnee,
                'est_valide': m.est_valide
            }
            for m in mesures
        ]
    
    def _archiver_evenements_externes(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """Archiver les événements externes"""
        evenements = EvenementExterne.objects.filter(
            zone=zone,
            date_evenement__gte=periode_debut,
            date_evenement__lte=periode_fin
        )
        
        return [
            {
                'id': e.id,
                'type_evenement': e.type_evenement,
                'intensite': e.intensite,
                'description': e.description,
                'date_evenement': e.date_evenement,
                'source': e.source,
                'metadata': e.metadata,
                'is_valide': e.is_valide,
                'is_traite': e.is_traite
            }
            for e in evenements
        ]
    
    def _archiver_fusions(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """Archiver les fusions de données"""
        fusions = FusionDonnees.objects.filter(
            zone=zone,
            date_creation__gte=periode_debut,
            date_creation__lte=periode_fin
        )
        
        return [
            {
                'id': f.id,
                'evenement_externe_id': f.evenement_externe.id,
                'score_erosion': f.score_erosion,
                'probabilite_erosion': f.probabilite_erosion,
                'facteurs_dominants': f.facteurs_dominants,
                'statut': f.statut,
                'date_creation': f.date_creation
            }
            for f in fusions
        ]
    
    def _archiver_predictions(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """Archiver les prédictions"""
        predictions = PredictionEnrichie.objects.filter(
            zone=zone,
            date_prediction__gte=periode_debut,
            date_prediction__lte=periode_fin
        )
        
        return [
            {
                'id': p.id,
                'erosion_predite': p.erosion_predite,
                'niveau_erosion': p.niveau_erosion,
                'confiance_pourcentage': p.confiance_pourcentage,
                'taux_erosion_pred_m_an': p.taux_erosion_pred_m_an,
                'recommandations': p.recommandations,
                'date_prediction': p.date_prediction
            }
            for p in predictions
        ]
    
    def _archiver_alertes(self, zone: Zone, periode_debut: datetime, periode_fin: datetime) -> List[Dict]:
        """Archiver les alertes"""
        alertes = AlerteEnrichie.objects.filter(
            zone=zone,
            date_creation__gte=periode_debut,
            date_creation__lte=periode_fin
        )
        
        return [
            {
                'id': a.id,
                'type': a.type,
                'niveau': a.niveau,
                'titre': a.titre,
                'description': a.description,
                'est_active': a.est_active,
                'est_resolue': a.est_resolue,
                'date_creation': a.date_creation
            }
            for a in alertes
        ]
