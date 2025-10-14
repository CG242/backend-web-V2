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
