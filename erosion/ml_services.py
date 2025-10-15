"""
Services pour l'intégration des APIs externes
"""
import requests
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.contrib.gis.geos import Point, Polygon
from .models import CleAPI, LogAPICall, DonneesEnvironnementales, DonneesCartographiques

logger = logging.getLogger(__name__)


class APIServiceBase:
    """Classe de base pour tous les services API"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.cle_api = self._get_api_key()
        self.url_base = self._get_base_url()
    
    def _get_api_key(self) -> Optional[str]:
        """Récupère la clé API pour ce service"""
        try:
            cle_obj = CleAPI.objects.get(service=self.service_name, actif=True)
            return cle_obj.cle_api
        except CleAPI.DoesNotExist:
            logger.warning(f"Aucune clé API trouvée pour {self.service_name}")
            return None
    
    def _get_base_url(self) -> str:
        """Récupère l'URL de base pour ce service"""
        try:
            cle_obj = CleAPI.objects.get(service=self.service_name, actif=True)
            return cle_obj.url_base
        except CleAPI.DoesNotExist:
            return ""
    
    def _log_api_call(self, endpoint: str, params: Dict, status: str, 
                     response_code: int = None, response_time: int = None,
                     data: Dict = None, error: str = None):
        """Enregistre l'appel API dans les logs"""
        LogAPICall.objects.create(
            service_api=self.service_name,
            endpoint_appele=endpoint,
            parametres_requete=params,
            statut_reponse=status,
            code_reponse_http=response_code,
            temps_reponse_ms=response_time,
            donnees_recues=data or {},
            message_erreur=error or ""
        )


class OpenMeteoService(APIServiceBase):
    """Service pour l'API Open-Meteo (météo)"""
    
    def __init__(self):
        super().__init__('open_meteo')
        self.url_base = "https://api.open-meteo.com/v1"
    
    def get_weather_data(self, latitude: float, longitude: float, 
                        start_date: str, end_date: str) -> Dict:
        """Récupère les données météorologiques"""
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'start_date': start_date,
            'end_date': end_date,
            'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,pressure_msl',
            'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum',
            'timezone': 'auto'
        }
        
        url = f"{self.url_base}/forecast"
        
        try:
            start_time = datetime.now()
            response = requests.get(url, params=params, timeout=30)
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                data = response.json()
                self._log_api_call(url, params, 'succes', 200, response_time, data)
                return self._process_weather_data(data)
            else:
                self._log_api_call(url, params, 'echec', response.status_code, response_time, error=f"HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            self._log_api_call(url, params, 'echec', error=str(e))
            logger.error(f"Erreur Open-Meteo: {e}")
            return {}
    
    def _process_weather_data(self, data: Dict) -> Dict:
        """Traite les données météorologiques"""
        processed = {
            'temperature_moyenne': None,
            'temperature_min': None,
            'temperature_max': None,
            'humidite_relative': None,
            'vitesse_vent': None,
            'direction_vent': None,
            'precipitation_totale': None,
            'pression_atmospherique': None,
            'donnees_completes': data
        }
        
        try:
            # Données quotidiennes
            if 'daily' in data:
                daily = data['daily']
                if 'temperature_2m_mean' in daily and daily['temperature_2m_mean']:
                    processed['temperature_moyenne'] = sum(daily['temperature_2m_mean']) / len(daily['temperature_2m_mean'])
                if 'temperature_2m_min' in daily and daily['temperature_2m_min']:
                    processed['temperature_min'] = min(daily['temperature_2m_min'])
                if 'temperature_2m_max' in daily and daily['temperature_2m_max']:
                    processed['temperature_max'] = max(daily['temperature_2m_max'])
                if 'precipitation_sum' in daily and daily['precipitation_sum']:
                    processed['precipitation_totale'] = sum(daily['precipitation_sum'])
            
            # Données horaires (moyennes)
            if 'hourly' in data:
                hourly = data['hourly']
                if 'relative_humidity_2m' in hourly and hourly['relative_humidity_2m']:
                    processed['humidite_relative'] = sum(hourly['relative_humidity_2m']) / len(hourly['relative_humidity_2m'])
                if 'wind_speed_10m' in hourly and hourly['wind_speed_10m']:
                    processed['vitesse_vent'] = sum(hourly['wind_speed_10m']) / len(hourly['wind_speed_10m'])
                if 'wind_direction_10m' in hourly and hourly['wind_direction_10m']:
                    processed['direction_vent'] = sum(hourly['wind_direction_10m']) / len(hourly['wind_direction_10m'])
                if 'pressure_msl' in hourly and hourly['pressure_msl']:
                    processed['pression_atmospherique'] = sum(hourly['pressure_msl']) / len(hourly['pressure_msl'])
                    
        except Exception as e:
            logger.error(f"Erreur traitement données météo: {e}")
        
        return processed


class OpenElevationService(APIServiceBase):
    """Service pour l'API Open-Elevation (topographie)"""
    
    def __init__(self):
        super().__init__('open_elevation')
        self.url_base = "https://api.open-elevation.com/api/v1"
    
    def get_elevation_data(self, points: List[Tuple[float, float]]) -> Dict:
        """Récupère les données d'élévation pour des points"""
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in points]
        
        payload = {"locations": locations}
        
        try:
            start_time = datetime.now()
            response = requests.post(f"{self.url_base}/lookup", json=payload, timeout=30)
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                data = response.json()
                self._log_api_call(f"{self.url_base}/lookup", payload, 'succes', 200, response_time, data)
                return self._process_elevation_data(data)
            else:
                self._log_api_call(f"{self.url_base}/lookup", payload, 'echec', response.status_code, response_time, error=f"HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            self._log_api_call(f"{self.url_base}/lookup", payload, 'echec', error=str(e))
            logger.error(f"Erreur Open-Elevation: {e}")
            return {}
    
    def _process_elevation_data(self, data: Dict) -> Dict:
        """Traite les données d'élévation"""
        processed = {
            'elevation_moyenne': None,
            'elevation_min': None,
            'elevation_max': None,
            'pente_moyenne': None,
            'donnees_completes': data
        }
        
        try:
            if 'results' in data and data['results']:
                elevations = [result['elevation'] for result in data['results'] if 'elevation' in result]
                
                if elevations:
                    processed['elevation_moyenne'] = sum(elevations) / len(elevations)
                    processed['elevation_min'] = min(elevations)
                    processed['elevation_max'] = max(elevations)
                    
                    # Calcul simple de la pente (différence max-min)
                    if len(elevations) > 1:
                        elevation_range = max(elevations) - min(elevations)
                        # Approximation de la pente en degrés
                        processed['pente_moyenne'] = elevation_range / len(elevations)
                        
        except Exception as e:
            logger.error(f"Erreur traitement données élévation: {e}")
        
        return processed


class NOAATidesService(APIServiceBase):
    """Service pour l'API NOAA Tides and Currents (marées)"""
    
    def __init__(self):
        super().__init__('noaa_tides')
        self.url_base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    
    def get_tide_data(self, station_id: str, start_date: str, end_date: str) -> Dict:
        """Récupère les données de marées"""
        params = {
            'product': 'water_level',
            'application': 'NOS.COOPS.TAC.WL',
            'begin_date': start_date,
            'end_date': end_date,
            'station': station_id,
            'time_zone': 'gmt',
            'units': 'metric',
            'interval': 'h',
            'format': 'json'
        }
        
        try:
            start_time = datetime.now()
            response = requests.get(self.url_base, params=params, timeout=30)
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                data = response.json()
                self._log_api_call(self.url_base, params, 'succes', 200, response_time, data)
                return self._process_tide_data(data)
            else:
                self._log_api_call(self.url_base, params, 'echec', response.status_code, response_time, error=f"HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            self._log_api_call(self.url_base, params, 'echec', error=str(e))
            logger.error(f"Erreur NOAA Tides: {e}")
            return {}
    
    def _process_tide_data(self, data: Dict) -> Dict:
        """Traite les données de marées"""
        processed = {
            'niveau_mer_moyen': None,
            'niveau_mer_min': None,
            'niveau_mer_max': None,
            'amplitude_maree': None,
            'donnees_completes': data
        }
        
        try:
            if 'data' in data and data['data']:
                levels = []
                for entry in data['data']:
                    if 'v' in entry and entry['v'] != '':
                        try:
                            levels.append(float(entry['v']))
                        except ValueError:
                            continue
                
                if levels:
                    processed['niveau_mer_moyen'] = sum(levels) / len(levels)
                    processed['niveau_mer_min'] = min(levels)
                    processed['niveau_mer_max'] = max(levels)
                    processed['amplitude_maree'] = max(levels) - min(levels)
                    
        except Exception as e:
            logger.error(f"Erreur traitement données marées: {e}")
        
        return processed


class NASAGIBSService(APIServiceBase):
    """Service pour l'API NASA GIBS (images satellites)"""
    
    def __init__(self):
        super().__init__('nasa_gibs')
        self.url_base = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
    
    def get_satellite_image(self, layer: str, bbox: Tuple[float, float, float, float], 
                          date: str, format_img: str = 'png') -> Dict:
        """Récupère une image satellite"""
        # Format: bbox = (min_lon, min_lat, max_lon, max_lat)
        min_lon, min_lat, max_lon, max_lat = bbox
        
        params = {
            'layer': layer,
            'style': 'default',
            'tilematrixset': 'GoogleMapsCompatible_Level9',
            'Service': 'WMTS',
            'Request': 'GetTile',
            'Version': '1.0.0',
            'Format': format_img,
            'TileMatrix': '9',
            'TileRow': '0',
            'TileCol': '0'
        }
        
        url = f"{self.url_base}/{layer}/default/GoogleMapsCompatible_Level9/{date}/0/0.{format_img}"
        
        try:
            start_time = datetime.now()
            response = requests.get(url, params=params, timeout=30)
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                # Sauvegarder l'image
                image_data = response.content
                self._log_api_call(url, params, 'succes', 200, response_time, {'image_size': len(image_data)})
                
                return {
                    'image_data': image_data,
                    'image_format': format_img,
                    'bbox': bbox,
                    'date': date,
                    'layer': layer,
                    'donnees_completes': {'url': url, 'params': params}
                }
            else:
                self._log_api_call(url, params, 'echec', response.status_code, response_time, error=f"HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            self._log_api_call(url, params, 'echec', error=str(e))
            logger.error(f"Erreur NASA GIBS: {e}")
            return {}


class CopernicusMarineService(APIServiceBase):
    """Service pour l'API Copernicus Marine (courants marins)"""
    
    def __init__(self):
        super().__init__('copernicus_marine')
        self.url_base = "https://nrt.cmems-du.eu/motu-web/Motu"
    
    def get_ocean_data(self, latitude: float, longitude: float, 
                      start_date: str, end_date: str) -> Dict:
        """Récupère les données océaniques"""
        if not self.cle_api:
            logger.warning("Clé API Copernicus Marine manquante")
            return {}
        
        params = {
            'action': 'productdownload',
            'mode': 'console',
            'service': 'motu',
            'product': 'global-analysis-forecast-phy-001-024',
            'x_lo': longitude - 0.1,
            'x_hi': longitude + 0.1,
            'y_lo': latitude - 0.1,
            'y_hi': latitude + 0.1,
            't_lo': start_date,
            't_hi': end_date,
            'variable': 'thetao,so,uo,vo',
            'output': 'netcdf'
        }
        
        try:
            start_time = datetime.now()
            response = requests.get(self.url_base, params=params, 
                                  headers={'Authorization': f'Bearer {self.cle_api}'}, 
                                  timeout=60)
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if response.status_code == 200:
                data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'data': 'binary'}
                self._log_api_call(self.url_base, params, 'succes', 200, response_time, data)
                return self._process_ocean_data(data)
            else:
                self._log_api_call(self.url_base, params, 'echec', response.status_code, response_time, error=f"HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            self._log_api_call(self.url_base, params, 'echec', error=str(e))
            logger.error(f"Erreur Copernicus Marine: {e}")
            return {}
    
    def _process_ocean_data(self, data: Dict) -> Dict:
        """Traite les données océaniques"""
        # Cette méthode devrait traiter les données NetCDF
        # Pour l'instant, retournons des données simulées
        processed = {
            'vitesse_courant': None,
            'direction_courant': None,
            'salinite_surface': None,
            'temperature_eau': None,
            'donnees_completes': data
        }
        
        # TODO: Implémenter le traitement des données NetCDF
        logger.info("Traitement des données Copernicus Marine - à implémenter")
        
        return processed


class DataConsolidationService:
    """Service de consolidation des données environnementales"""
    
    def __init__(self):
        self.meteo_service = OpenMeteoService()
        self.elevation_service = OpenElevationService()
        self.tides_service = NOAATidesService()
        self.nasa_service = NASAGIBSService()
        self.marine_service = CopernicusMarineService()
    
    def collect_all_data(self, zone, start_date: str, end_date: str) -> Dict:
        """Collecte toutes les données pour une zone"""
        logger.info(f"Collecte des données pour la zone {zone.nom}")
        
        # Coordonnées de la zone
        if zone.geometrie:
            bbox = zone.geometrie.extent
            center_lon = (bbox[0] + bbox[2]) / 2
            center_lat = (bbox[1] + bbox[3]) / 2
        else:
            # Coordonnées par défaut (Arcachon)
            center_lon, center_lat = -1.1, 44.7
        
        # Points d'échantillonnage
        points = [
            (center_lat, center_lon),
            (center_lat + 0.01, center_lon + 0.01),
            (center_lat - 0.01, center_lon - 0.01)
        ]
        
        consolidated_data = {
            'zone_id': zone.id,
            'zone_nom': zone.nom,
            'periode_debut': start_date,
            'periode_fin': end_date,
            'date_collecte': timezone.now().isoformat(),
            'meteo': {},
            'topographie': {},
            'marines': {},
            'satellite': {},
            'erreurs': []
        }
        
        # Collecte des données météorologiques
        try:
            meteo_data = self.meteo_service.get_weather_data(center_lat, center_lon, start_date, end_date)
            consolidated_data['meteo'] = meteo_data
        except Exception as e:
            consolidated_data['erreurs'].append(f"Météo: {str(e)}")
            logger.error(f"Erreur collecte météo: {e}")
        
        # Collecte des données topographiques
        try:
            elevation_data = self.elevation_service.get_elevation_data(points)
            consolidated_data['topographie'] = elevation_data
        except Exception as e:
            consolidated_data['erreurs'].append(f"Topographie: {str(e)}")
            logger.error(f"Erreur collecte topographie: {e}")
        
        # Collecte des données de marées (station fictive pour l'exemple)
        try:
            tide_data = self.tides_service.get_tide_data("8729108", start_date, end_date)  # Station exemple
            consolidated_data['marines'] = tide_data
        except Exception as e:
            consolidated_data['erreurs'].append(f"Marées: {str(e)}")
            logger.error(f"Erreur collecte marées: {e}")
        
        # Collecte des images satellites
        try:
            if zone.geometrie:
                bbox = zone.geometrie.extent
                satellite_data = self.nasa_service.get_satellite_image(
                    "MODIS_Terra_CorrectedReflectance_TrueColor", 
                    bbox, 
                    start_date
                )
                consolidated_data['satellite'] = satellite_data
        except Exception as e:
            consolidated_data['erreurs'].append(f"Satellite: {str(e)}")
            logger.error(f"Erreur collecte satellite: {e}")
        
        return consolidated_data
    
    def save_consolidated_data(self, zone, consolidated_data: Dict) -> DonneesEnvironnementales:
        """Sauvegarde les données consolidées"""
        
        # Extraire les données météorologiques
        meteo = consolidated_data.get('meteo', {})
        topo = consolidated_data.get('topographie', {})
        marine = consolidated_data.get('marines', {})
        
        # Créer l'objet DonneesEnvironnementales
        donnees_env = DonneesEnvironnementales.objects.create(
            zone=zone,
            periode_debut=datetime.fromisoformat(consolidated_data['periode_debut'].replace('Z', '+00:00')),
            periode_fin=datetime.fromisoformat(consolidated_data['periode_fin'].replace('Z', '+00:00')),
            
            # Données météorologiques
            temperature_moyenne=meteo.get('temperature_moyenne'),
            temperature_min=meteo.get('temperature_min'),
            temperature_max=meteo.get('temperature_max'),
            humidite_relative=meteo.get('humidite_relative'),
            vitesse_vent=meteo.get('vitesse_vent'),
            direction_vent=meteo.get('direction_vent'),
            precipitation_totale=meteo.get('precipitation_totale'),
            pression_atmospherique=meteo.get('pression_atmospherique'),
            
            # Données marines
            niveau_mer_moyen=marine.get('niveau_mer_moyen'),
            niveau_mer_min=marine.get('niveau_mer_min'),
            niveau_mer_max=marine.get('niveau_mer_max'),
            amplitude_maree=marine.get('amplitude_maree'),
            
            # Données topographiques
            elevation_moyenne=topo.get('elevation_moyenne'),
            elevation_min=topo.get('elevation_min'),
            elevation_max=topo.get('elevation_max'),
            pente_moyenne=topo.get('pente_moyenne'),
            
            # Données complètes
            donnees_completes=consolidated_data
        )
        
        return donnees_env


# ============================================================================
# SERVICES MACHINE LEARNING POUR PRÉDICTION D'ÉROSION
# ============================================================================

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count
from datetime import datetime, timedelta

from .models import (
    Zone, HistoriqueErosion, Capteur, Mesure, ModeleML, Prediction,
    CapteurArduino, MesureArduino, DonneesEnvironnementales
)


class MLPredictionService:
    """Service de prédiction d'érosion basé sur Machine Learning"""
    
    def __init__(self):
        self.models_dir = Path(settings.BASE_DIR) / 'ml_models'
        self.models_dir.mkdir(exist_ok=True)
        self.scaler = StandardScaler()
    
    def predire_erosion(self, zone_id: int, features: Dict = None, horizon_jours: int = 30) -> Prediction:
        """
        Prédit l'érosion pour une zone donnée
        
        Args:
            zone_id: ID de la zone
            features: Features supplémentaires (optionnel)
            horizon_jours: Horizon de prédiction en jours
            
        Returns:
            Objet Prediction créé
        """
        logger.info(f"Prédiction d'érosion pour la zone {zone_id}")
        
        try:
            # Récupérer la zone
            zone = Zone.objects.get(id=zone_id)
            
            # Récupérer le modèle ML actif
            modele_ml = self._get_active_model()
            if not modele_ml:
                raise ValueError("Aucun modèle ML actif trouvé")
            
            # Charger le modèle
            model = self._load_model(modele_ml)
            if not model:
                raise ValueError(f"Impossible de charger le modèle {modele_ml.nom}")
            
            # Préparer les features
            features_prepared = self._prepare_features(zone, features, modele_ml)
            
            # Calculer la prédiction
            prediction_result = self._calculate_prediction(
                model, features_prepared, horizon_jours, modele_ml
            )
            
            # Créer l'objet Prediction
            prediction = Prediction.objects.create(
                zone=zone,
                modele_ml=modele_ml,
                horizon_jours=horizon_jours,
                taux_erosion_pred_m_an=prediction_result['prediction'],
                taux_erosion_min_m_an=prediction_result['min'],
                taux_erosion_max_m_an=prediction_result['max'],
                confiance_pourcentage=prediction_result['confidence'],
                score_confiance=prediction_result['score'],
                features_entree=features_prepared,
                parametres_prediction={
                    'horizon_jours': horizon_jours,
                    'features_count': len(features_prepared),
                    'model_version': modele_ml.version
                },
                commentaires=f"Prédiction générée par {modele_ml.nom} v{modele_ml.version}"
            )
            
            # Mettre à jour les statistiques du modèle
            modele_ml.nombre_predictions += 1
            modele_ml.date_derniere_utilisation = timezone.now()
            modele_ml.save()
            
            logger.info(f"Prédiction créée avec succès: {prediction.id}")
            return prediction
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            raise
    
    def _get_active_model(self) -> Optional[ModeleML]:
        """Récupère le modèle ML actif"""
        try:
            return ModeleML.objects.get(statut='actif')
        except ModeleML.DoesNotExist:
            logger.warning("Aucun modèle ML actif trouvé")
            return None
    
    def _load_model(self, modele_ml: ModeleML):
        """Charge le modèle depuis le fichier"""
        try:
            model_path = self.models_dir / modele_ml.chemin_fichier
            if not model_path.exists():
                logger.error(f"Fichier modèle non trouvé: {model_path}")
                return None
            
            model = joblib.load(model_path)
            logger.info(f"Modèle {modele_ml.nom} chargé avec succès")
            return model
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle: {e}")
            return None
    
    def _prepare_features(self, zone: Zone, features: Dict, modele_ml: ModeleML) -> Dict:
        """Prépare les features pour la prédiction"""
        logger.info(f"Préparation des features pour la zone {zone.nom}")
        
        # Features de base de la zone
        prepared_features = {
            'superficie_km2': zone.superficie_km2,
            'niveau_risque_numerique': self._encode_risk_level(zone.niveau_risque),
        }
        
        # Features des capteurs Arduino (dernières mesures)
        capteurs_features = self._get_capteur_features(zone)
        prepared_features.update(capteurs_features)
        
        # Features historiques d'érosion
        historique_features = self._get_historique_features(zone)
        prepared_features.update(historique_features)
        
        # Features environnementales récentes
        env_features = self._get_environmental_features(zone)
        prepared_features.update(env_features)
        
        # Features supplémentaires fournies par l'utilisateur
        if features:
            prepared_features.update(features)
        
        # Filtrer selon les features utilisées par le modèle
        if modele_ml.features_utilisees:
            filtered_features = {
                key: value for key, value in prepared_features.items()
                if key in modele_ml.features_utilisees
            }
            prepared_features = filtered_features
        
        logger.info(f"Features préparées: {list(prepared_features.keys())}")
        return prepared_features
    
    def _encode_risk_level(self, niveau_risque: str) -> float:
        """Encode le niveau de risque en valeur numérique"""
        mapping = {
            'faible': 1.0,
            'modere': 2.0,
            'eleve': 3.0,
            'critique': 4.0
        }
        return mapping.get(niveau_risque, 1.0)
    
    def _get_capteur_features(self, zone: Zone) -> Dict:
        """Récupère les features des capteurs Arduino"""
        features = {}
        
        # Récupérer les dernières mesures des capteurs Arduino
        capteurs = CapteurArduino.objects.filter(zone=zone, etat='actif')
        
        for capteur in capteurs:
            derniere_mesure = MesureArduino.objects.filter(
                capteur=capteur
            ).order_by('-timestamp').first()
            
            if derniere_mesure:
                # Features basées sur le type de capteur
                if capteur.type_capteur == 'temperature':
                    features['temperature_actuelle'] = derniere_mesure.valeur
                elif capteur.type_capteur == 'humidite':
                    features['humidite_actuelle'] = derniere_mesure.humidite or derniere_mesure.valeur
                elif capteur.type_capteur == 'pression':
                    features['pression_actuelle'] = derniere_mesure.valeur
                elif capteur.type_capteur == 'ph':
                    features['ph_actuel'] = derniere_mesure.valeur
                elif capteur.type_capteur == 'salinite':
                    features['salinite_actuelle'] = derniere_mesure.valeur
                
                # Moyennes sur les 7 derniers jours
                date_limite = timezone.now() - timedelta(days=7)
                mesures_recentes = MesureArduino.objects.filter(
                    capteur=capteur,
                    timestamp__gte=date_limite
                )
                
                if mesures_recentes.exists():
                    if capteur.type_capteur == 'temperature':
                        features['temperature_moyenne_7j'] = mesures_recentes.aggregate(
                            avg=Avg('valeur')
                        )['avg']
                    elif capteur.type_capteur == 'humidite':
                        features['humidite_moyenne_7j'] = mesures_recentes.aggregate(
                            avg=Avg('humidite')
                        )['avg'] or mesures_recentes.aggregate(avg=Avg('valeur'))['avg']
        
        return features
    
    def _get_historique_features(self, zone: Zone) -> Dict:
        """Récupère les features de l'historique d'érosion"""
        features = {}
        
        # Dernière mesure d'érosion
        derniere_erosion = HistoriqueErosion.objects.filter(
            zone=zone
        ).order_by('-date_mesure').first()
        
        if derniere_erosion:
            features['derniere_erosion_m_an'] = derniere_erosion.taux_erosion_m_an
            features['precision_derniere_mesure'] = derniere_erosion.precision_m
        
        # Moyenne sur les 12 derniers mois
        date_limite = timezone.now() - timedelta(days=365)
        historique_recent = HistoriqueErosion.objects.filter(
            zone=zone,
            date_mesure__gte=date_limite
        )
        
        if historique_recent.exists():
            stats = historique_recent.aggregate(
                avg=Avg('taux_erosion_m_an'),
                min_val=Min('taux_erosion_m_an'),
                max_val=Max('taux_erosion_m_an'),
                count=Count('taux_erosion_m_an')
            )
            
            features['erosion_moyenne_12m'] = stats['avg']
            features['erosion_min_12m'] = stats['min_val']
            features['erosion_max_12m'] = stats['max_val']
            features['nombre_mesures_12m'] = stats['count']
        
        return features
    
    def _get_environmental_features(self, zone: Zone) -> Dict:
        """Récupère les features environnementales"""
        features = {}
        
        # Données environnementales récentes (dernières 30 jours)
        date_limite = timezone.now() - timedelta(days=30)
        donnees_env = DonneesEnvironnementales.objects.filter(
            zone=zone,
            periode_debut__gte=date_limite
        ).order_by('-periode_debut').first()
        
        if donnees_env:
            features.update({
                'temperature_moyenne_env': donnees_env.temperature_moyenne,
                'vitesse_vent_env': donnees_env.vitesse_vent,
                'precipitation_totale_env': donnees_env.precipitation_totale,
                'niveau_mer_moyen_env': donnees_env.niveau_mer_moyen,
                'elevation_moyenne_env': donnees_env.elevation_moyenne,
            })
        
        return features
    
    def _calculate_prediction(self, model, features: Dict, horizon_jours: int, modele_ml: ModeleML) -> Dict:
        """Calcule la prédiction avec le modèle"""
        try:
            # Convertir les features en array numpy
            feature_names = modele_ml.features_utilisees or list(features.keys())
            feature_values = [features.get(name, 0.0) for name in feature_names]
            X = np.array([feature_values]).reshape(1, -1)
            
            # Normaliser les features si nécessaire
            if hasattr(model, 'scaler_') and model.scaler_:
                X = model.scaler_.transform(X)
            
            # Prédiction principale
            prediction = model.predict(X)[0]
            
            # Calcul de l'intervalle de confiance
            if hasattr(model, 'predict_proba'):
                # Pour les modèles qui supportent la prédiction de probabilité
                proba = model.predict_proba(X)[0]
                confidence = np.max(proba) * 100
            else:
                # Estimation basée sur la variance du modèle
                if hasattr(model, 'estimators_'):
                    # Random Forest: utiliser la variance des arbres
                    predictions = [tree.predict(X)[0] for tree in model.estimators_]
                    std_dev = np.std(predictions)
                    confidence = max(0, min(100, 100 - std_dev * 10))
                else:
                    # Régression linéaire: estimation basique
                    confidence = 75.0
            
            # Calculer l'intervalle de confiance (±2σ)
            if hasattr(model, 'estimators_'):
                # Random Forest: utiliser les prédictions des arbres
                predictions = [tree.predict(X)[0] for tree in model.estimators_]
                std_dev = np.std(predictions)
                margin = 2 * std_dev
            else:
                # Estimation basique pour la régression linéaire
                margin = abs(prediction) * 0.2  # 20% de marge
            
            min_pred = max(0, prediction - margin)
            max_pred = prediction + margin
            
            return {
                'prediction': float(prediction),
                'min': float(min_pred),
                'max': float(max_pred),
                'confidence': float(confidence),
                'score': float(confidence / 100)
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul de prédiction: {e}")
            # Retourner une prédiction par défaut en cas d'erreur
            return {
                'prediction': 0.1,  # 0.1 m/an par défaut
                'min': 0.05,
                'max': 0.15,
                'confidence': 50.0,
                'score': 0.5
            }


class MLTrainingService:
    """Service d'entraînement des modèles ML"""
    
    def __init__(self):
        self.models_dir = Path(settings.BASE_DIR) / 'ml_models'
        self.models_dir.mkdir(exist_ok=True)
    
    def train_models(self) -> Dict:
        """
        Entraîne les modèles Random Forest et Régression Linéaire
        
        Returns:
            Dictionnaire avec les résultats d'entraînement
        """
        logger.info("Début de l'entraînement des modèles ML")
        
        results = {
            'random_forest': None,
            'regression_lineaire': None,
            'errors': []
        }
        
        try:
            # Préparer les données d'entraînement
            X, y = self._prepare_training_data()
            
            if len(X) < 10:  # Minimum de données pour l'entraînement
                raise ValueError("Pas assez de données pour l'entraînement (minimum 10 échantillons)")
            
            # Diviser les données
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Entraîner Random Forest
            results['random_forest'] = self._train_random_forest(X_train, X_test, y_train, y_test)
            
            # Entraîner Régression Linéaire
            results['regression_lineaire'] = self._train_linear_regression(X_train, X_test, y_train, y_test)
            
            # Sélectionner le meilleur modèle
            best_model = self._select_best_model(results)
            if best_model:
                best_model.marquer_comme_actif()
                logger.info(f"Modèle {best_model.nom} marqué comme actif")
            
            logger.info("Entraînement terminé avec succès")
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")
            results['errors'].append(str(e))
            return results
    
    def _prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Prépare les données d'entraînement"""
        logger.info("Préparation des données d'entraînement")
        
        training_data = []
        target_values = []
        
        # Récupérer toutes les zones avec des données historiques
        zones = Zone.objects.all()
        
        for zone in zones:
            # Récupérer l'historique d'érosion de la zone
            historique = HistoriqueErosion.objects.filter(zone=zone).order_by('-date_mesure')
            
            for mesure in historique:
                # Préparer les features pour cette mesure
                features = self._prepare_features_for_training(zone, mesure.date_mesure)
                
                if features:  # Si on a des features valides
                    training_data.append(features)
                    target_values.append(mesure.taux_erosion_m_an)
        
        if not training_data:
            raise ValueError("Aucune donnée d'entraînement trouvée")
        
        X = np.array(training_data)
        y = np.array(target_values)
        
        logger.info(f"Données d'entraînement préparées: {X.shape[0]} échantillons, {X.shape[1]} features")
        return X, y
    
    def _prepare_features_for_training(self, zone: Zone, date_mesure) -> List[float]:
        """Prépare les features pour une mesure d'entraînement"""
        features = []
        
        # Features de base de la zone (toujours les mêmes)
        features.extend([
            zone.superficie_km2,
            self._encode_risk_level(zone.niveau_risque),
        ])
        
        # Features des capteurs (mesures autour de la date de mesure)
        # On s'assure d'avoir toujours le même nombre de features
        capteur_features = self._get_capteur_features_for_date(zone, date_mesure)
        features.extend(capteur_features)
        
        # Features environnementales (toujours les mêmes)
        env_features = self._get_environmental_features_for_date(zone, date_mesure)
        features.extend(env_features)
        
        return features
    
    def _get_capteur_features_for_date(self, zone: Zone, date_mesure) -> List[float]:
        """Récupère les features des capteurs pour une date donnée"""
        features = []
        
        # Période de recherche (±7 jours autour de la date)
        date_debut = date_mesure - timedelta(days=7)
        date_fin = date_mesure + timedelta(days=7)
        
        # Types de capteurs fixes pour s'assurer d'avoir toujours le même nombre de features
        capteur_types = ['temperature', 'humidite', 'pression', 'ph', 'salinite']
        
        for capteur_type in capteur_types:
            # Chercher un capteur de ce type dans la zone
            capteur = CapteurArduino.objects.filter(
                zone=zone, 
                type_capteur=capteur_type, 
                etat='actif'
            ).first()
            
            if capteur:
                mesures = MesureArduino.objects.filter(
                    capteur=capteur,
                    timestamp__range=[date_debut, date_fin]
                )
                
                if mesures.exists():
                    features.append(mesures.aggregate(avg=Avg('valeur'))['avg'] or 0.0)
                else:
                    features.append(0.0)
            else:
                features.append(0.0)  # Pas de capteur de ce type
        
        return features
    
    def _get_environmental_features_for_date(self, zone: Zone, date_mesure) -> List[float]:
        """Récupère les features environnementales pour une date donnée"""
        features = []
        
        # Données environnementales autour de la date
        date_debut = date_mesure - timedelta(days=30)
        date_fin = date_mesure + timedelta(days=30)
        
        donnees_env = DonneesEnvironnementales.objects.filter(
            zone=zone,
            periode_debut__range=[date_debut, date_fin]
        ).first()
        
        if donnees_env:
            features.extend([
                donnees_env.temperature_moyenne or 0.0,
                donnees_env.vitesse_vent or 0.0,
                donnees_env.precipitation_totale or 0.0,
                donnees_env.niveau_mer_moyen or 0.0,
                donnees_env.elevation_moyenne or 0.0,
            ])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0, 0.0])
        
        return features
    
    def _encode_risk_level(self, niveau_risque: str) -> float:
        """Encode le niveau de risque en valeur numérique"""
        mapping = {
            'faible': 1.0,
            'modere': 2.0,
            'eleve': 3.0,
            'critique': 4.0
        }
        return mapping.get(niveau_risque, 1.0)
    
    def _train_random_forest(self, X_train, X_test, y_train, y_test) -> Dict:
        """Entraîne un modèle Random Forest"""
        logger.info("Entraînement du modèle Random Forest")
        
        try:
            # Créer et entraîner le modèle
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train, y_train)
            
            # Évaluer le modèle
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Sauvegarder le modèle
            model_filename = f"random_forest_{timezone.now().strftime('%Y%m%d_%H%M%S')}.joblib"
            model_path = self.models_dir / model_filename
            joblib.dump(model, model_path)
            
            # Créer l'objet ModeleML
            modele_ml = ModeleML.objects.create(
                nom="Random Forest Erosion",
                version=f"1.{timezone.now().strftime('%Y%m%d')}",
                type_modele='random_forest',
                statut='inactif',
                chemin_fichier=model_filename,
                precision_score=r2,
                parametres_entrainement={
                    'n_estimators': 100,
                    'max_depth': 10,
                    'mse': mse,
                    'r2_score': r2,
                    'train_samples': len(X_train),
                    'test_samples': len(X_test)
                },
                features_utilisees=list(range(X_train.shape[1])),  # Indices des features
                commentaires=f"Modèle Random Forest entraîné le {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            logger.info(f"Random Forest entraîné - R²: {r2:.3f}, MSE: {mse:.3f}")
            
            return {
                'model_id': modele_ml.id,
                'model_name': modele_ml.nom,
                'r2_score': r2,
                'mse': mse,
                'model_path': str(model_path)
            }
            
        except Exception as e:
            logger.error(f"Erreur entraînement Random Forest: {e}")
            return {'error': str(e)}
    
    def _train_linear_regression(self, X_train, X_test, y_train, y_test) -> Dict:
        """Entraîne un modèle de Régression Linéaire"""
        logger.info("Entraînement du modèle Régression Linéaire")
        
        try:
            # Normaliser les features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Créer et entraîner le modèle
            model = LinearRegression()
            model.fit(X_train_scaled, y_train)
            
            # Ajouter le scaler au modèle pour la prédiction
            model.scaler_ = scaler
            
            # Évaluer le modèle
            y_pred = model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Sauvegarder le modèle
            model_filename = f"linear_regression_{timezone.now().strftime('%Y%m%d_%H%M%S')}.joblib"
            model_path = self.models_dir / model_filename
            joblib.dump(model, model_path)
            
            # Créer l'objet ModeleML
            modele_ml = ModeleML.objects.create(
                nom="Régression Linéaire Erosion",
                version=f"1.{timezone.now().strftime('%Y%m%d')}",
                type_modele='regression_lineaire',
                statut='inactif',
                chemin_fichier=model_filename,
                precision_score=r2,
                parametres_entrainement={
                    'mse': mse,
                    'r2_score': r2,
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'features_scaled': True
                },
                features_utilisees=list(range(X_train.shape[1])),  # Indices des features
                commentaires=f"Modèle Régression Linéaire entraîné le {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            logger.info(f"Régression Linéaire entraînée - R²: {r2:.3f}, MSE: {mse:.3f}")
            
            return {
                'model_id': modele_ml.id,
                'model_name': modele_ml.nom,
                'r2_score': r2,
                'mse': mse,
                'model_path': str(model_path)
            }
            
        except Exception as e:
            logger.error(f"Erreur entraînement Régression Linéaire: {e}")
            return {'error': str(e)}
    
    def _select_best_model(self, results: Dict) -> Optional[ModeleML]:
        """Sélectionne le meilleur modèle basé sur le R² score"""
        best_model = None
        best_score = -float('inf')
        
        for model_type, result in results.items():
            if result and 'r2_score' in result and not result.get('error'):
                if result['r2_score'] > best_score:
                    best_score = result['r2_score']
                    best_model = ModeleML.objects.get(id=result['model_id'])
        
        return best_model