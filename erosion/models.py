from django.contrib.gis.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta
import json


class Utilisateur(AbstractUser):
    """Modèle utilisateur personnalisé"""
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('scientifique', 'Scientifique'),
        ('technicien', 'Technicien'),
        ('observateur', 'Observateur'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='observateur')
    telephone = models.CharField(max_length=20, blank=True)
    organisation = models.CharField(max_length=100, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"


class Zone(models.Model):
    """Zone géographique surveillée avec géométrie PostGIS"""
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    geometrie = models.PolygonField(srid=4326, null=True, blank=True)  # Géométrie PostGIS en WGS84
    superficie_km2 = models.FloatField(validators=[MinValueValidator(0)])
    niveau_risque = models.CharField(
        max_length=20,
        choices=[
            ('faible', 'Faible'),
            ('modere', 'Modéré'),
            ('eleve', 'Élevé'),
            ('critique', 'Critique'),
        ],
        default='faible'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ['nom']
    
    def __str__(self):
        return self.nom


class HistoriqueErosion(models.Model):
    """Historique des mesures d'érosion par zone"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='historique_erosion')
    date_mesure = models.DateTimeField()
    taux_erosion_m_an = models.FloatField(help_text="Taux d'érosion en mètres par an")
    methode_mesure = models.CharField(
        max_length=50,
        choices=[
            ('gps', 'GPS'),
            ('lidar', 'LIDAR'),
            ('photogrammetrie', 'Photogrammétrie'),
            ('manuel', 'Mesure manuelle'),
        ]
    )
    precision_m = models.FloatField(help_text="Précision de la mesure en mètres")
    commentaires = models.TextField(blank=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Historique d'érosion"
        verbose_name_plural = "Historiques d'érosion"
        ordering = ['-date_mesure']
    
    def __str__(self):
        return f"{self.zone.nom} - {self.date_mesure.strftime('%Y-%m-%d')}"


class Capteur(models.Model):
    """Capteur de surveillance environnementale avec position PostGIS"""
    TYPE_CHOICES = [
        ('temperature', 'Température'),
        ('salinite', 'Salinité'),
        ('houle', 'Houle'),
        ('vent', 'Vent'),
        ('pluviometrie', 'Pluviométrie'),
        ('niveau_mer', 'Niveau de mer'),
        ('ph', 'pH'),
        ('turbidite', 'Turbidité'),
    ]
    
    ETAT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('maintenance', 'En maintenance'),
        ('defaillant', 'Défaillant'),
    ]
    
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='capteurs')
    position = models.PointField(srid=4326, null=True, blank=True)  # Position PostGIS en WGS84
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default='actif')
    frequence_mesure_min = models.IntegerField(
        default=60,
        help_text="Fréquence de mesure en minutes"
    )
    precision = models.FloatField(help_text="Précision du capteur")
    unite_mesure = models.CharField(max_length=10)
    date_installation = models.DateTimeField(default=timezone.now)
    date_derniere_maintenance = models.DateTimeField(null=True, blank=True)
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Capteur"
        verbose_name_plural = "Capteurs"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom} ({self.type})"


class Mesure(models.Model):
    """Mesure effectuée par un capteur"""
    capteur = models.ForeignKey(Capteur, on_delete=models.CASCADE, related_name='mesures')
    valeur = models.FloatField()
    unite = models.CharField(max_length=10)
    timestamp = models.DateTimeField(default=timezone.now)
    qualite_donnee = models.CharField(
        max_length=20,
        choices=[
            ('excellente', 'Excellente'),
            ('bonne', 'Bonne'),
            ('moyenne', 'Moyenne'),
            ('faible', 'Faible'),
            ('douteuse', 'Douteuse'),
        ],
        default='bonne'
    )
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Mesure"
        verbose_name_plural = "Mesures"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['capteur', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.capteur.nom} - {self.valeur} {self.unite} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"


class Prediction(models.Model):
    """Prédiction d'érosion basée sur les données"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='predictions')
    date_prediction = models.DateTimeField(default=timezone.now)
    horizon_jours = models.IntegerField(help_text="Horizon de prédiction en jours")
    taux_erosion_pred_m_an = models.FloatField(help_text="Taux d'érosion prédit en m/an")
    confiance_pourcentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Niveau de confiance en pourcentage"
    )
    modele_utilise = models.CharField(max_length=100)
    parametres_modele = models.JSONField(default=dict, blank=True)
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Prédiction"
        verbose_name_plural = "Prédictions"
        ordering = ['-date_prediction']
    
    def __str__(self):
        return f"{self.zone.nom} - Prédiction {self.horizon_jours}j ({self.date_prediction.strftime('%Y-%m-%d')})"


class TendanceLongTerme(models.Model):
    """Analyse des tendances à long terme"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='tendances')
    periode_debut = models.DateTimeField()
    periode_fin = models.DateTimeField()
    taux_erosion_moyen_m_an = models.FloatField()
    tendance = models.CharField(
        max_length=20,
        choices=[
            ('croissante', 'Croissante'),
            ('stable', 'Stable'),
            ('decroissante', 'Décroissante'),
        ]
    )
    facteurs_influence = models.JSONField(default=list, blank=True)
    date_analyse = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "Tendance long terme"
        verbose_name_plural = "Tendances long terme"
        ordering = ['-date_analyse']
    
    def __str__(self):
        return f"{self.zone.nom} - Tendance {self.tendance} ({self.periode_debut.year}-{self.periode_fin.year})"


class Alerte(models.Model):
    """Système d'alerte pour les événements critiques"""
    NIVEAU_CHOICES = [
        ('info', 'Information'),
        ('attention', 'Attention'),
        ('alerte', 'Alerte'),
        ('critique', 'Critique'),
    ]
    
    TYPE_CHOICES = [
        ('erosion_acceleree', 'Érosion accélérée'),
        ('capteur_defaillant', 'Capteur défaillant'),
        ('donnee_anormale', 'Donnée anormale'),
        ('maintenance_requise', 'Maintenance requise'),
        ('evenement_climatique', 'Événement climatique'),
    ]
    
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='alertes')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES)
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date_creation = models.DateTimeField(default=timezone.now)
    date_resolution = models.DateTimeField(null=True, blank=True)
    est_resolue = models.BooleanField(default=False)
    utilisateur_creation = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='alertes_crees'
    )
    utilisateur_resolution = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='alertes_resolues'
    )
    
    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.titre} - {self.niveau}"


class EvenementClimatique(models.Model):
    """Événements climatiques impactant l'érosion"""
    TYPE_CHOICES = [
        ('tempete', 'Tempête'),
        ('ouragan', 'Ouragan'),
        ('cyclone', 'Cyclone'),
        ('tsunami', 'Tsunami'),
        ('maree_exceptionnelle', 'Marée exceptionnelle'),
        ('secheresse', 'Sécheresse'),
        ('inondation', 'Inondation'),
    ]
    
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    intensite = models.CharField(
        max_length=20,
        choices=[
            ('faible', 'Faible'),
            ('moderee', 'Modérée'),
            ('forte', 'Forte'),
            ('extreme', 'Extrême'),
        ]
    )
    zones_impactees = models.ManyToManyField(Zone, related_name='evenements_climatiques')
    description = models.TextField()
    impact_erosion_estime = models.FloatField(
        null=True, 
        blank=True,
        help_text="Impact estimé sur l'érosion en mètres"
    )
    
    class Meta:
        verbose_name = "Événement climatique"
        verbose_name_plural = "Événements climatiques"
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"{self.nom} ({self.type}) - {self.date_debut.strftime('%Y-%m-%d')}"


class JournalAction(models.Model):
    """Journal des actions effectuées sur le système"""
    ACTION_CHOICES = [
        ('creation', 'Création'),
        ('modification', 'Modification'),
        ('suppression', 'Suppression'),
        ('consultation', 'Consultation'),
        ('export', 'Export'),
        ('import', 'Import'),
    ]
    
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    objet_type = models.CharField(max_length=50)  # Type d'objet modifié
    objet_id = models.IntegerField(null=True, blank=True)  # ID de l'objet
    description = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Journal d'action"
        verbose_name_plural = "Journal des actions"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['utilisateur', 'timestamp']),
            models.Index(fields=['objet_type', 'objet_id']),
        ]
    
    def __str__(self):
        return f"{self.utilisateur} - {self.action} {self.objet_type} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"


# ============================================================================
# NOUVEAUX MODÈLES POUR DONNÉES CARTOGRAPHIQUES ET ENVIRONNEMENTALES
# ============================================================================

class CleAPI(models.Model):
    """Gestion sécurisée des clés API externes"""
    SERVICE_CHOICES = [
        ('open_meteo', 'Open-Meteo'),
        ('open_elevation', 'Open-Elevation'),
        ('noaa_tides', 'NOAA Tides and Currents'),
        ('nasa_gibs', 'NASA GIBS'),
        ('sentinel_hub', 'Sentinel Hub'),
        ('copernicus_marine', 'Copernicus Marine'),
        ('copernicus_land', 'Copernicus Land Monitoring'),
    ]
    
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES, unique=True)
    cle_api = models.TextField(help_text="Clé API chiffrée")
    url_base = models.URLField(help_text="URL de base de l'API")
    limite_requetes_heure = models.PositiveIntegerField(default=1000)
    limite_requetes_jour = models.PositiveIntegerField(default=10000)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Clé API"
        verbose_name_plural = "Clés API"
    
    def __str__(self):
        return f"{self.get_service_display()} - {'Actif' if self.actif else 'Inactif'}"


class DonneesCartographiques(models.Model):
    """Données cartographiques pour une zone spécifique"""
    TYPE_DONNEES_CHOICES = [
        ('satellite', 'Image satellite'),
        ('substrat', 'Substrat/Couverture terrestre'),
        ('hydrographie', 'Hydrographie'),
        ('topographie', 'Topographie'),
        ('bathymetrie', 'Bathymétrie'),
    ]
    
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='donnees_cartographiques')
    type_donnees = models.CharField(max_length=20, choices=TYPE_DONNEES_CHOICES)
    source = models.CharField(max_length=100, help_text="Source des données (ex: NASA GIBS, Copernicus)")
    resolution = models.FloatField(help_text="Résolution en mètres")
    format_donnees = models.CharField(max_length=20, default='geojson')
    
    # Géométrie de la zone couverte
    geometrie_couverte = models.PolygonField(srid=4326)
    
    # Données brutes (GeoJSON, raster, etc.)
    donnees_brutes = models.JSONField(default=dict)
    
    # Métadonnées
    date_acquisition = models.DateTimeField()
    date_traitement = models.DateTimeField(auto_now_add=True)
    qualite_donnees = models.CharField(
        max_length=20,
        choices=[
            ('excellente', 'Excellente'),
            ('bonne', 'Bonne'),
            ('moyenne', 'Moyenne'),
            ('faible', 'Faible'),
        ],
        default='bonne'
    )
    
    # Fichiers associés
    fichier_raster = models.FileField(upload_to='cartographie/raster/', blank=True, null=True)
    fichier_vectoriel = models.FileField(upload_to='cartographie/vectoriel/', blank=True, null=True)
    
    class Meta:
        verbose_name = "Données cartographiques"
        verbose_name_plural = "Données cartographiques"
        ordering = ['-date_acquisition']
        indexes = [
            models.Index(fields=['zone', 'type_donnees']),
            models.Index(fields=['date_acquisition']),
        ]
    
    def __str__(self):
        return f"{self.zone.nom} - {self.get_type_donnees_display()} ({self.source})"


class DonneesEnvironnementales(models.Model):
    """Données environnementales consolidées pour une zone"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='donnees_environnementales')
    date_collecte = models.DateTimeField(auto_now_add=True)
    periode_debut = models.DateTimeField()
    periode_fin = models.DateTimeField()
    
    # Données météorologiques (Open-Meteo)
    temperature_moyenne = models.FloatField(null=True, blank=True, help_text="°C")
    temperature_min = models.FloatField(null=True, blank=True, help_text="°C")
    temperature_max = models.FloatField(null=True, blank=True, help_text="°C")
    humidite_relative = models.FloatField(null=True, blank=True, help_text="%")
    vitesse_vent = models.FloatField(null=True, blank=True, help_text="m/s")
    direction_vent = models.FloatField(null=True, blank=True, help_text="degrés")
    precipitation_totale = models.FloatField(null=True, blank=True, help_text="mm")
    pression_atmospherique = models.FloatField(null=True, blank=True, help_text="hPa")
    
    # Données marines (NOAA, Copernicus Marine)
    niveau_mer_moyen = models.FloatField(null=True, blank=True, help_text="mètres")
    niveau_mer_min = models.FloatField(null=True, blank=True, help_text="mètres")
    niveau_mer_max = models.FloatField(null=True, blank=True, help_text="mètres")
    amplitude_maree = models.FloatField(null=True, blank=True, help_text="mètres")
    vitesse_courant = models.FloatField(null=True, blank=True, help_text="m/s")
    direction_courant = models.FloatField(null=True, blank=True, help_text="degrés")
    salinite_surface = models.FloatField(null=True, blank=True, help_text="PSU")
    temperature_eau = models.FloatField(null=True, blank=True, help_text="°C")
    
    # Données topographiques (Open-Elevation)
    elevation_moyenne = models.FloatField(null=True, blank=True, help_text="mètres")
    elevation_min = models.FloatField(null=True, blank=True, help_text="mètres")
    elevation_max = models.FloatField(null=True, blank=True, help_text="mètres")
    pente_moyenne = models.FloatField(null=True, blank=True, help_text="degrés")
    
    # Données consolidées (JSON complet)
    donnees_completes = models.JSONField(default=dict, help_text="Toutes les données consolidées")
    
    # Indicateurs calculés
    indice_erosion_potentiel = models.FloatField(null=True, blank=True, help_text="Indice calculé")
    facteurs_risque = models.JSONField(default=list, help_text="Facteurs de risque identifiés")
    
    class Meta:
        verbose_name = "Données environnementales"
        verbose_name_plural = "Données environnementales"
        ordering = ['-date_collecte']
        indexes = [
            models.Index(fields=['zone', 'date_collecte']),
            models.Index(fields=['periode_debut', 'periode_fin']),
        ]
    
    def __str__(self):
        return f"{self.zone.nom} - {self.date_collecte.strftime('%Y-%m-%d %H:%M')}"


class AnalyseErosion(models.Model):
    """Analyse d'érosion enrichie avec toutes les données"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='analyses_erosion')
    donnees_environnementales = models.ForeignKey(DonneesEnvironnementales, on_delete=models.CASCADE)
    
    # Paramètres d'analyse
    date_analyse = models.DateTimeField(auto_now_add=True)
    horizon_prediction_jours = models.PositiveIntegerField(default=30)
    modele_utilise = models.CharField(max_length=100, default="Modèle enrichi multi-facteurs")
    
    # Résultats de l'analyse
    taux_erosion_predit = models.FloatField(help_text="mètres/an")
    confiance_prediction = models.FloatField(help_text="%", validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Facteurs d'influence
    facteur_meteo = models.FloatField(null=True, blank=True, help_text="Contribution météo")
    facteur_marin = models.FloatField(null=True, blank=True, help_text="Contribution marine")
    facteur_topographique = models.FloatField(null=True, blank=True, help_text="Contribution topographie")
    facteur_substrat = models.FloatField(null=True, blank=True, help_text="Contribution substrat")
    
    # Recommandations
    recommandations = models.JSONField(default=list, help_text="Recommandations générées")
    niveau_urgence = models.CharField(
        max_length=20,
        choices=[
            ('faible', 'Faible'),
            ('modere', 'Modéré'),
            ('eleve', 'Élevé'),
            ('critique', 'Critique'),
        ],
        default='faible'
    )
    
    # Données détaillées
    calculs_detaille = models.JSONField(default=dict, help_text="Calculs détaillés")
    
    class Meta:
        verbose_name = "Analyse d'érosion"
        verbose_name_plural = "Analyses d'érosion"
        ordering = ['-date_analyse']
    
    def __str__(self):
        return f"{self.zone.nom} - {self.date_analyse.strftime('%Y-%m-%d')} - {self.taux_erosion_predit:.2f}m/an"


class LogAPICall(models.Model):
    """Journal des appels aux APIs externes"""
    STATUT_CHOICES = [
        ('succes', 'Succès'),
        ('echec', 'Échec'),
        ('timeout', 'Timeout'),
        ('quota_depasse', 'Quota dépassé'),
    ]
    
    service_api = models.CharField(max_length=50)
    endpoint_appele = models.URLField()
    parametres_requete = models.JSONField(default=dict)
    statut_reponse = models.CharField(max_length=20, choices=STATUT_CHOICES)
    code_reponse_http = models.PositiveIntegerField(null=True, blank=True)
    temps_reponse_ms = models.PositiveIntegerField(null=True, blank=True)
    donnees_recues = models.JSONField(default=dict, blank=True)
    message_erreur = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Log API"
        verbose_name_plural = "Logs API"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['service_api', 'timestamp']),
            models.Index(fields=['statut_reponse']),
        ]
    
    def __str__(self):
        return f"{self.service_api} - {self.statut_reponse} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# ============================================================================
# MODÈLES POUR CAPTEURS ARDUINO NANO ESP32 - DONNÉES RÉELLES
# ============================================================================

class CapteurArduino(models.Model):
    """Capteur Arduino Nano ESP32 avec gestion Wi-Fi"""
    ETAT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('detected', 'Détecté'),
        ('maintenance', 'En maintenance'),
        ('defaillant', 'Défaillant'),
        ('hors_ligne', 'Hors ligne'),
        ('erreur_wifi', 'Erreur Wi-Fi'),
    ]
    
    TYPE_CAPTEUR_CHOICES = [
        ('temperature', 'Température'),
        ('humidite', 'Humidité'),
        ('pression', 'Pression atmosphérique'),
        ('luminosite', 'Luminosité'),
        ('vent_vitesse', 'Vitesse du vent'),
        ('vent_direction', 'Direction du vent'),
        ('pluviometrie', 'Pluviométrie'),
        ('niveau_mer', 'Niveau de mer'),
        ('salinite', 'Salinité'),
        ('ph', 'pH'),
        ('turbidite', 'Turbidité'),
        ('gps', 'GPS'),
        ('accelerometre', 'Accéléromètre'),
        ('gyroscope', 'Gyroscope'),
    ]
    
    # Informations de base
    nom = models.CharField(max_length=100, unique=True)
    type_capteur = models.CharField(max_length=20, choices=TYPE_CAPTEUR_CHOICES)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='capteurs_arduino')
    position = models.PointField(srid=4326, null=True, blank=True)
    
    # Configuration Arduino
    adresse_mac = models.CharField(max_length=17, unique=True, help_text="Adresse MAC du module ESP32")
    adresse_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Adresse IP assignée")
    ssid_wifi = models.CharField(max_length=50, help_text="Nom du réseau Wi-Fi")
    mot_de_passe_wifi = models.CharField(max_length=100, help_text="Mot de passe Wi-Fi (chiffré)")
    
    # Paramètres de mesure
    frequence_mesure_secondes = models.PositiveIntegerField(default=300, help_text="Fréquence en secondes")
    precision = models.FloatField(help_text="Précision du capteur")
    unite_mesure = models.CharField(max_length=10)
    valeur_min = models.FloatField(null=True, blank=True, help_text="Valeur minimale valide")
    valeur_max = models.FloatField(null=True, blank=True, help_text="Valeur maximale valide")
    
    # État et maintenance
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default='inactif')
    date_installation = models.DateTimeField(default=timezone.now)
    date_derniere_maintenance = models.DateTimeField(null=True, blank=True)
    date_derniere_communication = models.DateTimeField(null=True, blank=True)
    
    # Configuration technique
    version_firmware = models.CharField(max_length=20, default='1.0.0')
    tension_batterie = models.FloatField(null=True, blank=True, help_text="Tension en volts")
    niveau_signal_wifi = models.IntegerField(null=True, blank=True, help_text="Niveau signal Wi-Fi (dBm)")
    
    # Métadonnées
    commentaires = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Capteur Arduino"
        verbose_name_plural = "Capteurs Arduino"
        ordering = ['nom']
        indexes = [
            models.Index(fields=['adresse_mac']),
            models.Index(fields=['zone', 'type_capteur']),
            models.Index(fields=['etat', 'actif']),
            models.Index(fields=['date_derniere_communication']),
        ]
    
    def save(self, *args, **kwargs):
        # Générer automatiquement un nom clair basé sur sensor_id et sensor_type
        if not self.nom or self.nom.startswith('TEMPERATURE_') or self.nom.startswith('DHT11_') or self.nom.startswith('HUMIDITY_') or self.nom.startswith('RAIN_'):
            sensor_names = {
                "temperature": "Température",
                "humidite": "Humidité", 
                "humidity": "Humidité",
                "pression": "Pression",
                "luminosite": "Luminosité",
                "vent_vitesse": "Vitesse Vent",
                "vent_direction": "Direction Vent",
                "pluviometrie": "Pluie",
                "rain": "Pluie",
                "niveau_mer": "Niveau Mer",
                "salinite": "Salinité",
                "ph": "pH",
                "turbidite": "Turbidité",
                "gps": "GPS",
                "accelerometre": "Accéléromètre",
                "gyroscope": "Gyroscope",
                "dht11": "DHT11",
            }
            
            # Extraire sensor_id du nom existant ou utiliser le type_capteur
            if '_' in self.nom:
                sensor_id = self.nom.split('_')[-1]
            else:
                sensor_id = self.nom.split(' ')[0] if ' ' in self.nom else self.type_capteur.upper()
            
            readable_type = sensor_names.get(self.type_capteur.lower(), self.type_capteur.capitalize())
            
            # Générer le nouveau nom : "TEMP_001 (Température)"
            base_nom = f"{sensor_id} ({readable_type})"
            
            # Vérifier l'unicité et ajouter un suffixe si nécessaire
            counter = 1
            self.nom = base_nom
            while CapteurArduino.objects.filter(nom=self.nom).exclude(pk=self.pk).exists():
                self.nom = f"{base_nom} #{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom} ({self.get_type_capteur_display()}) - {self.adresse_mac}"
    
    @property
    def est_en_ligne(self):
        """Vérifie si le capteur est en ligne (communication récente)"""
        if not self.date_derniere_communication:
            return False
        timeout = timedelta(minutes=30)  # 30 minutes de timeout
        return timezone.now() - self.date_derniere_communication < timeout
    
    @property
    def derniere_mesure(self):
        """Retourne la dernière mesure reçue"""
        return self.mesures_arduino.order_by('-timestamp').first()


class MesureArduino(models.Model):
    """Mesure reçue d'un capteur Arduino"""
    QUALITE_CHOICES = [
        ('excellente', 'Excellente'),
        ('bonne', 'Bonne'),
        ('moyenne', 'Moyenne'),
        ('faible', 'Faible'),
        ('douteuse', 'Douteuse'),
        ('invalide', 'Invalide'),
        ('interpolee', 'Interpolée'),
        ('derniere_connue', 'Dernière valeur connue'),
    ]
    
    SOURCE_CHOICES = [
        ('capteur_reel', 'Capteur réel'),
        ('interpolation', 'Interpolation automatique'),
        ('derniere_valeur', 'Dernière valeur connue'),
        ('valeur_defaut', 'Valeur par défaut'),
    ]
    
    # Références
    capteur = models.ForeignKey(CapteurArduino, on_delete=models.CASCADE, related_name='mesures_arduino')
    
    # Données de mesure
    valeur = models.FloatField(help_text="Valeur principale (température)")
    humidite = models.FloatField(null=True, blank=True, help_text="Humidité relative (%)")
    unite = models.CharField(max_length=10)
    timestamp = models.DateTimeField()
    timestamp_reception = models.DateTimeField(auto_now_add=True, help_text="Timestamp de réception par le serveur")
    
    # Métadonnées de qualité
    qualite_donnee = models.CharField(max_length=20, choices=QUALITE_CHOICES, default='bonne')
    source_donnee = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='capteur_reel')
    
    # Données techniques Arduino
    tension_batterie = models.FloatField(null=True, blank=True, help_text="Tension batterie au moment de la mesure")
    niveau_signal_wifi = models.IntegerField(null=True, blank=True, help_text="Niveau signal Wi-Fi")
    temperature_cpu = models.FloatField(null=True, blank=True, help_text="Température CPU Arduino")
    uptime_secondes = models.PositiveIntegerField(null=True, blank=True, help_text="Temps de fonctionnement")
    
    # Validation et filtrage
    est_valide = models.BooleanField(default=True)
    erreur_validation = models.TextField(blank=True, help_text="Message d'erreur si invalide")
    
    # Données brutes reçues
    donnees_brutes = models.JSONField(default=dict, help_text="Données JSON brutes reçues")
    
    # Métadonnées
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Mesure Arduino"
        verbose_name_plural = "Mesures Arduino"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['capteur', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['qualite_donnee', 'est_valide']),
            models.Index(fields=['source_donnee']),
        ]
        unique_together = ['capteur', 'timestamp']  # Évite les doublons
    
    def __str__(self):
        return f"{self.capteur.nom} - {self.valeur} {self.unite} ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
    
    def save(self, *args, **kwargs):
        """Valide automatiquement la mesure lors de la sauvegarde"""
        if self.source_donnee == 'capteur_reel':
            self._valider_mesure()
        super().save(*args, **kwargs)
    
    def _valider_mesure(self):
        """Valide la mesure selon les critères du capteur"""
        capteur = self.capteur
        
        # Vérification des limites
        if capteur.valeur_min is not None and self.valeur < capteur.valeur_min:
            self.est_valide = False
            self.erreur_validation = f"Valeur {self.valeur} inférieure au minimum {capteur.valeur_min}"
            self.qualite_donnee = 'invalide'
            return
        
        if capteur.valeur_max is not None and self.valeur > capteur.valeur_max:
            self.est_valide = False
            self.erreur_validation = f"Valeur {self.valeur} supérieure au maximum {capteur.valeur_max}"
            self.qualite_donnee = 'invalide'
            return
        
        # Vérification de la cohérence temporelle
        if self.timestamp > timezone.now() + timedelta(minutes=5):
            self.est_valide = False
            self.erreur_validation = "Timestamp dans le futur"
            self.qualite_donnee = 'douteuse'
            return
        
        # Vérification de la batterie
        if self.tension_batterie is not None and self.tension_batterie < 3.0:
            self.qualite_donnee = 'faible'
            self.commentaires += " Batterie faible."
        
        # Vérification du signal Wi-Fi
        if self.niveau_signal_wifi is not None and self.niveau_signal_wifi < -80:
            self.qualite_donnee = 'moyenne'
            self.commentaires += " Signal Wi-Fi faible."


class DonneesManquantes(models.Model):
    """Gestion des données manquantes et complétion automatique"""
    TYPE_COMPLETION_CHOICES = [
        ('interpolation', 'Interpolation linéaire'),
        ('derniere_valeur', 'Dernière valeur connue'),
        ('moyenne_mobile', 'Moyenne mobile'),
        ('valeur_defaut', 'Valeur par défaut'),
        ('extrapolation', 'Extrapolation'),
    ]
    
    capteur = models.ForeignKey(CapteurArduino, on_delete=models.CASCADE, related_name='donnees_manquantes')
    periode_debut = models.DateTimeField()
    periode_fin = models.DateTimeField()
    duree_manque_minutes = models.PositiveIntegerField(help_text="Durée du manque en minutes")
    
    # Données de complétion
    type_completion = models.CharField(max_length=20, choices=TYPE_COMPLETION_CHOICES)
    nombre_valeurs_completees = models.PositiveIntegerField(default=0)
    valeurs_completees = models.JSONField(default=list, help_text="Liste des valeurs complétées")
    
    # Métadonnées
    date_detection = models.DateTimeField(auto_now_add=True)
    date_completion = models.DateTimeField(null=True, blank=True)
    est_completee = models.BooleanField(default=False)
    qualite_completion = models.CharField(max_length=20, choices=MesureArduino.QUALITE_CHOICES, default='moyenne')
    
    # Données de référence utilisées
    derniere_valeur_connue = models.FloatField(null=True, blank=True)
    derniere_timestamp_connu = models.DateTimeField(null=True, blank=True)
    prochaine_valeur_connue = models.FloatField(null=True, blank=True)
    prochain_timestamp_connu = models.DateTimeField(null=True, blank=True)
    
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Données manquantes"
        verbose_name_plural = "Données manquantes"
        ordering = ['-date_detection']
        indexes = [
            models.Index(fields=['capteur', 'date_detection']),
            models.Index(fields=['est_completee']),
            models.Index(fields=['periode_debut', 'periode_fin']),
        ]
    
    def __str__(self):
        return f"{self.capteur.nom} - Manque {self.duree_manque_minutes}min ({self.periode_debut.strftime('%Y-%m-%d %H:%M')})"


class LogCapteurArduino(models.Model):
    """Journal des événements des capteurs Arduino"""
    TYPE_EVENEMENT_CHOICES = [
        ('connexion', 'Connexion'),
        ('deconnexion', 'Déconnexion'),
        ('mesure_recue', 'Mesure reçue'),
        ('mesure_invalide', 'Mesure invalide'),
        ('erreur_wifi', 'Erreur Wi-Fi'),
        ('batterie_faible', 'Batterie faible'),
        ('maintenance', 'Maintenance'),
        ('mise_a_jour_firmware', 'Mise à jour firmware'),
        ('erreur_systeme', 'Erreur système'),
    ]
    
    NIVEAU_CHOICES = [
        ('info', 'Information'),
        ('attention', 'Attention'),
        ('erreur', 'Erreur'),
        ('critique', 'Critique'),
    ]
    
    capteur = models.ForeignKey(CapteurArduino, on_delete=models.CASCADE, related_name='logs')
    type_evenement = models.CharField(max_length=30, choices=TYPE_EVENEMENT_CHOICES)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default='info')
    
    # Détails de l'événement
    message = models.TextField()
    donnees_contexte = models.JSONField(default=dict, help_text="Données contextuelles de l'événement")
    
    # Métadonnées
    timestamp = models.DateTimeField(auto_now_add=True)
    adresse_ip_source = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    
    class Meta:
        verbose_name = "Log Capteur Arduino"
        verbose_name_plural = "Logs Capteurs Arduino"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['capteur', 'timestamp']),
            models.Index(fields=['type_evenement', 'niveau']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.capteur.nom} - {self.get_type_evenement_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


# ============================================================================
# MODÈLES POUR ÉVÉNEMENTS EXTERNES ET FUSION DE DONNÉES
# ============================================================================

class EvenementExterne(models.Model):
    """Événements externes reçus d'applications tierces (pluie, tempête, vent, vagues, etc.)"""
    
    TYPE_CHOICES = [
        ('pluie', 'Pluie'),
        ('tempete', 'Tempête'),
        ('vent_fort', 'Vent fort'),
        ('vague', 'Vague élevée'),
        ('maree_exceptionnelle', 'Marée exceptionnelle'),
        ('secheresse', 'Sécheresse'),
        ('inondation', 'Inondation'),
        ('tsunami', 'Tsunami'),
        ('ouragan', 'Ouragan'),
        ('cyclone', 'Cyclone'),
        ('autre', 'Autre'),
    ]
    
    INTENSITE_CHOICES = [
        ('faible', 'Faible (0-25%)'),
        ('moderee', 'Modérée (26-50%)'),
        ('forte', 'Forte (51-75%)'),
        ('extreme', 'Extrême (76-100%)'),
    ]
    
    # Informations de base
    type_evenement = models.CharField(max_length=50, choices=TYPE_CHOICES)
    intensite = models.FloatField(
        help_text="Intensité de 0 à 100",
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    intensite_categorie = models.CharField(
        max_length=20, 
        choices=INTENSITE_CHOICES,
        help_text="Catégorie d'intensité calculée automatiquement"
    )
    description = models.TextField(blank=True, null=True)
    
    # Géolocalisation et timing
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='evenements_externes')
    date_evenement = models.DateTimeField(help_text="Date/heure de l'événement")
    date_reception = models.DateTimeField(auto_now_add=True, help_text="Date/heure de réception par le backend")
    
    # Métadonnées et provenance
    source = models.CharField(max_length=100, help_text="Source de l'événement (ex: MeteoFrance, NOAA)")
    source_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID unique dans la source")
    metadata = models.JSONField(default=dict, blank=True, help_text="Métadonnées supplémentaires")
    
    # Données techniques
    duree_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Durée estimée en minutes")
    rayon_impact_km = models.FloatField(null=True, blank=True, help_text="Rayon d'impact en kilomètres")
    
    # Statut et validation
    is_simulation = models.BooleanField(default=False, help_text="Marquer si c'est une donnée de test/simulation")
    is_valide = models.BooleanField(default=True, help_text="Événement validé par le système")
    is_traite = models.BooleanField(default=False, help_text="Événement traité pour fusion/analyse")
    
    # Liens avec autres données
    evenements_lies = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=False,
        help_text="Événements liés ou corrélés"
    )
    
    # Métadonnées système
    commentaires = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Événement externe"
        verbose_name_plural = "Événements externes"
        ordering = ['-date_evenement']
        indexes = [
            models.Index(fields=['zone', 'date_evenement']),
            models.Index(fields=['type_evenement', 'intensite']),
            models.Index(fields=['source', 'date_reception']),
            models.Index(fields=['is_traite', 'is_valide']),
        ]
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement la catégorie d'intensité
        if self.intensite <= 25:
            self.intensite_categorie = 'faible'
        elif self.intensite <= 50:
            self.intensite_categorie = 'moderee'
        elif self.intensite <= 75:
            self.intensite_categorie = 'forte'
        else:
            self.intensite_categorie = 'extreme'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_type_evenement_display()} {self.intensite}% - {self.zone.nom} ({self.date_evenement.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def est_recent(self):
        """Vérifie si l'événement est récent (moins de 24h)"""
        from datetime import timedelta
        return timezone.now() - self.date_evenement < timedelta(hours=24)
    
    @property
    def niveau_risque(self):
        """Calcule le niveau de risque basé sur l'intensité et le type"""
        if self.intensite >= 80:
            return 'critique'
        elif self.intensite >= 60:
            return 'eleve'
        elif self.intensite >= 40:
            return 'modere'
        else:
            return 'faible'


class FusionDonnees(models.Model):
    """Résultat de la fusion entre événements externes et mesures Arduino"""
    
    STATUT_CHOICES = [
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('erreur', 'Erreur'),
        ('annulee', 'Annulée'),
    ]
    
    # Références
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='fusions_donnees')
    evenement_externe = models.ForeignKey(
        EvenementExterne, 
        on_delete=models.CASCADE, 
        related_name='fusions'
    )
    
    # Période de fusion
    periode_debut = models.DateTimeField()
    periode_fin = models.DateTimeField()
    
    # Données fusionnées
    mesures_arduino_count = models.PositiveIntegerField(default=0, help_text="Nombre de mesures Arduino utilisées")
    evenements_externes_count = models.PositiveIntegerField(default=0, help_text="Nombre d'événements externes utilisés")
    
    # Résultats de l'analyse
    score_erosion = models.FloatField(help_text="Score d'érosion calculé (0-100)")
    probabilite_erosion = models.FloatField(
        help_text="Probabilité d'érosion (0-1)",
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    facteurs_dominants = models.JSONField(default=list, help_text="Facteurs les plus influents")
    
    # Métadonnées
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_cours')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Fusion de données"
        verbose_name_plural = "Fusions de données"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['zone', 'date_creation']),
            models.Index(fields=['statut', 'score_erosion']),
        ]
    
    def __str__(self):
        return f"Fusion {self.zone.nom} - {self.score_erosion:.1f}% ({self.date_creation.strftime('%Y-%m-%d %H:%M')})"


class PredictionEnrichie(models.Model):
    """Prédictions d'érosion enrichies avec fusion d'événements et mesures"""
    
    NIVEAU_CONFIANCE_CHOICES = [
        ('faible', 'Faible (< 60%)'),
        ('moyenne', 'Moyenne (60-80%)'),
        ('elevee', 'Élevée (80-95%)'),
        ('tres_elevee', 'Très élevée (> 95%)'),
    ]
    
    # Références
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='predictions_enrichies')
    fusion_donnees = models.ForeignKey(
        FusionDonnees, 
        on_delete=models.CASCADE, 
        related_name='predictions_enrichies'
    )
    
    # Prédiction principale
    erosion_predite = models.BooleanField(help_text="Érosion prédite (True/False)")
    niveau_erosion = models.CharField(
        max_length=20,
        choices=[
            ('faible', 'Faible'),
            ('modere', 'Modéré'),
            ('eleve', 'Élevé'),
            ('critique', 'Critique'),
        ]
    )
    confiance_pourcentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Niveau de confiance en pourcentage"
    )
    niveau_confiance = models.CharField(
        max_length=20, 
        choices=NIVEAU_CONFIANCE_CHOICES,
        help_text="Catégorie de confiance calculée automatiquement"
    )
    
    # Détails de la prédiction
    horizon_jours = models.PositiveIntegerField(help_text="Horizon de prédiction en jours")
    taux_erosion_pred_m_an = models.FloatField(help_text="Taux d'érosion prédit en m/an")
    
    # Facteurs d'influence
    facteur_evenements = models.FloatField(null=True, blank=True, help_text="Contribution des événements externes")
    facteur_mesures_arduino = models.FloatField(null=True, blank=True, help_text="Contribution des mesures Arduino")
    facteur_historique = models.FloatField(null=True, blank=True, help_text="Contribution de l'historique")
    
    # Recommandations
    recommandations = models.JSONField(default=list, help_text="Recommandations générées")
    actions_urgentes = models.JSONField(default=list, help_text="Actions urgentes recommandées")
    
    # Métadonnées
    modele_utilise = models.CharField(max_length=100, default="Modèle enrichi multi-facteurs")
    parametres_modele = models.JSONField(default=dict, blank=True)
    date_prediction = models.DateTimeField(auto_now_add=True)
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Prédiction enrichie"
        verbose_name_plural = "Prédictions enrichies"
        ordering = ['-date_prediction']
        indexes = [
            models.Index(fields=['zone', 'date_prediction']),
            models.Index(fields=['erosion_predite', 'niveau_erosion']),
            models.Index(fields=['confiance_pourcentage']),
        ]
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement le niveau de confiance
        if self.confiance_pourcentage < 60:
            self.niveau_confiance = 'faible'
        elif self.confiance_pourcentage < 80:
            self.niveau_confiance = 'moyenne'
        elif self.confiance_pourcentage < 95:
            self.niveau_confiance = 'elevee'
        else:
            self.niveau_confiance = 'tres_elevee'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.zone.nom} - Érosion: {'OUI' if self.erosion_predite else 'NON'} ({self.confiance_pourcentage:.1f}%) - {self.date_prediction.strftime('%Y-%m-%d')}"


class AlerteEnrichie(models.Model):
    """Alertes générées automatiquement basées sur les prédictions enrichies"""
    
    NIVEAU_CHOICES = [
        ('info', 'Information'),
        ('attention', 'Attention'),
        ('alerte', 'Alerte'),
        ('critique', 'Critique'),
        ('urgence', 'Urgence'),
    ]
    
    TYPE_CHOICES = [
        ('erosion_predite', 'Érosion prédite'),
        ('evenement_extreme', 'Événement extrême'),
        ('donnees_anormales', 'Données anormales'),
        ('capteur_defaillant', 'Capteur défaillant'),
        ('fusion_echec', 'Échec de fusion'),
        ('prediction_incertaine', 'Prédiction incertaine'),
    ]
    
    # Références
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='alertes_enrichies')
    prediction_enrichie = models.ForeignKey(
        PredictionEnrichie, 
        on_delete=models.CASCADE, 
        related_name='alertes',
        null=True, 
        blank=True
    )
    evenement_externe = models.ForeignKey(
        EvenementExterne, 
        on_delete=models.CASCADE, 
        related_name='alertes',
        null=True, 
        blank=True
    )
    
    # Détails de l'alerte
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES)
    titre = models.CharField(max_length=200)
    description = models.TextField()
    
    # Statut
    est_active = models.BooleanField(default=True)
    est_resolue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_resolution = models.DateTimeField(null=True, blank=True)
    
    # Actions
    actions_requises = models.JSONField(default=list, help_text="Actions requises")
    utilisateur_resolution = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='alertes_enrichies_resolues'
    )
    
    # Métadonnées
    donnees_contexte = models.JSONField(default=dict, help_text="Données contextuelles")
    commentaires = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Alerte enrichie"
        verbose_name_plural = "Alertes enrichies"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['zone', 'date_creation']),
            models.Index(fields=['niveau', 'est_active']),
            models.Index(fields=['type', 'est_resolue']),
        ]
    
    def __str__(self):
        return f"{self.titre} - {self.niveau} ({self.date_creation.strftime('%Y-%m-%d %H:%M')})"


class ArchiveDonnees(models.Model):
    """Archive des données pour l'IA et l'analyse historique"""
    
    TYPE_DONNEES_CHOICES = [
        ('mesures_arduino', 'Mesures Arduino'),
        ('evenements_externes', 'Événements externes'),
        ('fusions', 'Fusions de données'),
        ('predictions', 'Prédictions'),
        ('alertes', 'Alertes'),
    ]
    
    # Identification
    type_donnees = models.CharField(max_length=30, choices=TYPE_DONNEES_CHOICES)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='archives')
    
    # Période archivée
    periode_debut = models.DateTimeField()
    periode_fin = models.DateTimeField()
    
    # Données archivées
    nombre_elements = models.PositiveIntegerField(help_text="Nombre d'éléments archivés")
    taille_fichier_mb = models.FloatField(help_text="Taille du fichier en MB")
    format_archive = models.CharField(max_length=20, default='json', help_text="Format d'archive")
    
    # Métadonnées
    date_archivage = models.DateTimeField(auto_now_add=True)
    utilisateur_archivage = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='archives_creees'
    )
    chemin_fichier = models.CharField(max_length=500, help_text="Chemin vers le fichier d'archive")
    
    # Statut
    est_disponible = models.BooleanField(default=True)
    date_suppression = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées supplémentaires
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, help_text="Tags pour classification")
    
    class Meta:
        verbose_name = "Archive de données"
        verbose_name_plural = "Archives de données"
        ordering = ['-date_archivage']
        indexes = [
            models.Index(fields=['type_donnees', 'zone']),
            models.Index(fields=['periode_debut', 'periode_fin']),
            models.Index(fields=['date_archivage']),
        ]
    
    def __str__(self):
        return f"Archive {self.get_type_donnees_display()} - {self.zone.nom} ({self.periode_debut.strftime('%Y-%m-%d')} à {self.periode_fin.strftime('%Y-%m-%d')})"