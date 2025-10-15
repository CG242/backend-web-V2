from rest_framework import serializers
# from rest_framework_gis.serializers import GeoFeatureModelSerializer  # Désactivé temporairement
from .models import (
    Utilisateur, Zone, HistoriqueErosion, Capteur, Mesure,
    Prediction, ModeleML, TendanceLongTerme, Alerte, EvenementClimatique, JournalAction,
    CleAPI, DonneesCartographiques, DonneesEnvironnementales, 
    AnalyseErosion, LogAPICall,
    CapteurArduino, MesureArduino, DonneesManquantes, LogCapteurArduino,
    EvenementExterne, FusionDonnees, PredictionEnrichie, AlerteEnrichie, ArchiveDonnees
)


class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Utilisateur"""
    class Meta:
        model = Utilisateur
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'telephone', 'organisation', 'date_creation', 'date_modification',
            'is_active', 'is_staff', 'date_joined'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification', 'date_joined']


class ZoneSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Zone"""
    class Meta:
        model = Zone
        fields = [
            'id', 'nom', 'description', 'geometrie', 'superficie_km2',
            'niveau_risque', 'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']


class HistoriqueErosionSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle HistoriqueErosion"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    
    class Meta:
        model = HistoriqueErosion
        fields = [
            'id', 'zone', 'zone_nom', 'date_mesure', 'taux_erosion_m_an',
            'methode_mesure', 'precision_m', 'commentaires', 'utilisateur', 'utilisateur_nom'
        ]
        read_only_fields = ['id']


class CapteurSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Capteur"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    nombre_mesures = serializers.SerializerMethodField()
    derniere_mesure = serializers.SerializerMethodField()

    class Meta:
        model = Capteur
        fields = [
            'id', 'nom', 'type', 'zone', 'zone_nom', 'position', 'etat',
            'frequence_mesure_min', 'precision', 'unite_mesure',
            'date_installation', 'date_derniere_maintenance', 'commentaires',
            'nombre_mesures', 'derniere_mesure'
        ]
        read_only_fields = ['id', 'date_installation']
    
    def get_nombre_mesures(self, obj) -> int:
        """Retourne le nombre de mesures pour ce capteur"""
        return obj.mesures.count()
    
    def get_derniere_mesure(self, obj) -> dict | None:
        """Retourne la dernière mesure pour ce capteur"""
        derniere = obj.mesures.order_by('-timestamp').first()
        if derniere:
            return {
                'valeur': derniere.valeur,
                'unite': derniere.unite,
                'timestamp': derniere.timestamp
            }
        return None


class MesureSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Mesure"""
    capteur_nom = serializers.CharField(source='capteur.nom', read_only=True)
    capteur_type = serializers.CharField(source='capteur.type', read_only=True)
    zone_nom = serializers.CharField(source='capteur.zone.nom', read_only=True)
    
    class Meta:
        model = Mesure
        fields = [
            'id', 'capteur', 'capteur_nom', 'capteur_type', 'zone_nom',
            'valeur', 'unite', 'timestamp', 'qualite_donnee', 'commentaires'
        ]
        read_only_fields = ['id']


class PredictionSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Prediction (ancien modèle - à supprimer)"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    
    class Meta:
        model = Prediction
        fields = [
            'id', 'zone', 'zone_nom', 'date_prediction', 'horizon_jours',
            'taux_erosion_pred_m_an', 'confiance_pourcentage', 'modele_ml',
            'parametres_prediction', 'commentaires'
        ]
        read_only_fields = ['id']


class ModeleMLSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle ModeleML"""
    nombre_predictions = serializers.IntegerField(read_only=True)
    date_derniere_utilisation = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = ModeleML
        fields = [
            'id', 'nom', 'version', 'type_modele', 'statut', 'chemin_fichier',
            'precision_score', 'parametres_entrainement', 'features_utilisees',
            'date_creation', 'date_derniere_utilisation', 'nombre_predictions',
            'commentaires'
        ]
        read_only_fields = ['id', 'date_creation', 'date_derniere_utilisation', 'nombre_predictions']


class PredictionMLSerializer(serializers.ModelSerializer):
    """Serializer pour le nouveau modèle Prediction avec ML"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    modele_nom = serializers.CharField(source='modele_ml.nom', read_only=True)
    modele_version = serializers.CharField(source='modele_ml.version', read_only=True)
    modele_type = serializers.CharField(source='modele_ml.type_modele', read_only=True)
    intervalle_confiance = serializers.ReadOnlyField()
    
    class Meta:
        model = Prediction
        fields = [
            'id', 'zone', 'zone_nom', 'modele_ml', 'modele_nom', 'modele_version', 'modele_type',
            'date_prediction', 'horizon_jours', 'taux_erosion_pred_m_an',
            'taux_erosion_min_m_an', 'taux_erosion_max_m_an', 'intervalle_confiance',
            'confiance_pourcentage', 'score_confiance', 'features_entree',
            'parametres_prediction', 'commentaires'
        ]
        read_only_fields = ['id', 'date_prediction', 'intervalle_confiance']


class PredictionRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes de prédiction"""
    zone_id = serializers.IntegerField(help_text="ID de la zone pour laquelle faire la prédiction")
    horizon_jours = serializers.IntegerField(
        default=30,
        min_value=1,
        max_value=365,
        help_text="Horizon de prédiction en jours (1-365)"
    )
    features = serializers.DictField(
        child=serializers.FloatField(),
        help_text="Features supplémentaires pour la prédiction (optionnel)"
    )
    commentaires = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Commentaires sur la prédiction"
    )
    
    def validate_zone_id(self, value):
        """Valide que la zone existe"""
        try:
            Zone.objects.get(id=value)
        except Zone.DoesNotExist:
            raise serializers.ValidationError("La zone spécifiée n'existe pas.")
        return value
    
    def validate_features(self, value):
        """Valide les features supplémentaires"""
        # Vérifier que les features sont des valeurs numériques valides
        for key, val in value.items():
            if not isinstance(val, (int, float)):
                raise serializers.ValidationError(f"La feature '{key}' doit être numérique.")
            if not -1000 <= val <= 1000:  # Limite raisonnable pour éviter les valeurs aberrantes
                raise serializers.ValidationError(f"La feature '{key}' doit être entre -1000 et 1000.")
        return value


class TendanceLongTermeSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle TendanceLongTerme"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    
    class Meta:
        model = TendanceLongTerme
        fields = [
            'id', 'zone', 'zone_nom', 'periode_debut', 'periode_fin',
            'taux_erosion_moyen_m_an', 'tendance', 'facteurs_influence', 'date_analyse'
        ]
        read_only_fields = ['id']


class AlerteSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Alerte d'érosion côtière"""
    
    class Meta:
        model = Alerte
        fields = [
            'id',
            'titre',
            'description',
            'niveau_urgence',
            'latitude',
            'longitude',
            'zone',
            'date_creation',
            'date_mise_a_jour',
            'statut',
            'source',
            'donnees_meteo',
            'donnees_marines'
        ]
        read_only_fields = ['id', 'date_creation', 'date_mise_a_jour']


class EvenementClimatiqueSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle EvenementClimatique"""
    zones_impactees_noms = serializers.StringRelatedField(source='zones_impactees', many=True, read_only=True)
    
    class Meta:
        model = EvenementClimatique
        fields = [
            'id', 'nom', 'type', 'date_debut', 'date_fin', 'intensite',
            'zones_impactees', 'zones_impactees_noms', 'description', 'impact_erosion_estime'
        ]
        read_only_fields = ['id']


class JournalActionSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle JournalAction"""
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    
    class Meta:
        model = JournalAction
        fields = [
            'id', 'utilisateur', 'utilisateur_nom', 'action', 'objet_type',
            'objet_id', 'description', 'timestamp', 'ip_address'
        ]
        read_only_fields = ['id', 'timestamp']


# Serializers pour les statistiques et analyses
class StatistiquesZoneSerializer(serializers.Serializer):
    """Serializer pour les statistiques d'une zone"""
    zone_id = serializers.IntegerField()
    zone_nom = serializers.CharField()
    nombre_capteurs = serializers.IntegerField()
    nombre_mesures_total = serializers.IntegerField()
    derniere_mesure = serializers.DateTimeField()
    taux_erosion_moyen = serializers.FloatField()
    nombre_alertes_actives = serializers.IntegerField()
    niveau_risque = serializers.CharField()


class MesureStatistiqueSerializer(serializers.Serializer):
    """Serializer pour les statistiques de mesures"""
    capteur_id = serializers.IntegerField()
    capteur_nom = serializers.CharField()
    type_capteur = serializers.CharField()
    valeur_moyenne = serializers.FloatField()
    valeur_min = serializers.FloatField()
    valeur_max = serializers.FloatField()
    nombre_mesures = serializers.IntegerField()
    periode_debut = serializers.DateTimeField()
    periode_fin = serializers.DateTimeField()


# ============================================================================
# SÉRIALISEURS POUR LA DOCUMENTATION (ÉVITE LES PROBLÈMES AVEC drf-spectacular)
# ============================================================================

class ZoneDocSerializer(serializers.ModelSerializer):
    """Serializer pour la documentation des zones (sans géométrie)"""
    class Meta:
        model = Zone
        fields = [
            'id', 'nom', 'description', 'superficie_km2',
            'niveau_risque', 'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']


class CapteurDocSerializer(serializers.ModelSerializer):
    """Serializer pour la documentation des capteurs (sans géométrie)"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    nombre_mesures = serializers.SerializerMethodField()
    derniere_mesure = serializers.SerializerMethodField()

    class Meta:
        model = Capteur
        fields = [
            'id', 'nom', 'type', 'zone', 'zone_nom', 'etat',
            'frequence_mesure_min', 'precision', 'unite_mesure',
            'date_installation', 'date_derniere_maintenance', 'commentaires',
            'nombre_mesures', 'derniere_mesure'
        ]
        read_only_fields = ['id', 'date_installation']
    
    def get_nombre_mesures(self, obj) -> int:
        """Retourne le nombre de mesures pour ce capteur"""
        return obj.mesures.count()
    
    def get_derniere_mesure(self, obj) -> dict | None:
        """Retourne la dernière mesure pour ce capteur"""
        derniere = obj.mesures.order_by('-timestamp').first()
        if derniere:
            return {
                'valeur': derniere.valeur,
                'unite': derniere.unite,
                'timestamp': derniere.timestamp
            }
        return None


class DonneesCartographiquesDocSerializer(serializers.ModelSerializer):
    """Serializer pour la documentation des données cartographiques (sans géométrie)"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    
    class Meta:
        model = DonneesCartographiques
        fields = [
            'id', 'zone', 'zone_nom', 'type_donnees', 'source', 'resolution',
            'format_donnees', 'donnees_brutes',
            'date_acquisition', 'date_traitement', 'qualite_donnees',
            'fichier_raster', 'fichier_vectoriel'
        ]
        read_only_fields = ['id', 'date_traitement']


# ============================================================================
# SÉRIALISEURS PRINCIPAUX (AVEC GÉOMÉTRIE)
# ============================================================================

class CleAPISerializer(serializers.ModelSerializer):
    """Serializer pour la gestion des clés API"""
    cle_api_masquee = serializers.SerializerMethodField()
    
    class Meta:
        model = CleAPI
        fields = [
            'id', 'service', 'cle_api_masquee', 'url_base', 
            'limite_requetes_heure', 'limite_requetes_jour', 
            'actif', 'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']
    
    def get_cle_api_masquee(self, obj):
        """Masque la clé API pour la sécurité"""
        if obj.cle_api:
            return f"{obj.cle_api[:8]}...{obj.cle_api[-4:]}" if len(obj.cle_api) > 12 else "***"
        return "Non configurée"


class DonneesCartographiquesSerializer(serializers.ModelSerializer):
    """Serializer pour les données cartographiques"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    
    class Meta:
        model = DonneesCartographiques
        fields = [
            'id', 'zone', 'zone_nom', 'type_donnees', 'source', 'resolution',
            'format_donnees', 'geometrie_couverte', 'donnees_brutes',
            'date_acquisition', 'date_traitement', 'qualite_donnees',
            'fichier_raster', 'fichier_vectoriel'
        ]
        read_only_fields = ['id', 'date_traitement']


class DonneesEnvironnementalesSerializer(serializers.ModelSerializer):
    """Serializer pour les données environnementales consolidées"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    nombre_erreurs = serializers.SerializerMethodField()
    
    class Meta:
        model = DonneesEnvironnementales
        fields = [
            'id', 'zone', 'zone_nom', 'date_collecte', 'periode_debut', 'periode_fin',
            'temperature_moyenne', 'temperature_min', 'temperature_max', 'humidite_relative',
            'vitesse_vent', 'direction_vent', 'precipitation_totale', 'pression_atmospherique',
            'niveau_mer_moyen', 'niveau_mer_min', 'niveau_mer_max', 'amplitude_maree',
            'vitesse_courant', 'direction_courant', 'salinite_surface', 'temperature_eau',
            'elevation_moyenne', 'elevation_min', 'elevation_max', 'pente_moyenne',
            'donnees_completes', 'indice_erosion_potentiel', 'facteurs_risque', 'nombre_erreurs'
        ]
        read_only_fields = ['id', 'date_collecte']
    
    def get_nombre_erreurs(self, obj):
        """Compte le nombre d'erreurs lors de la collecte"""
        erreurs = obj.donnees_completes.get('erreurs', [])
        return len(erreurs)


class AnalyseErosionSerializer(serializers.ModelSerializer):
    """Serializer pour les analyses d'érosion enrichies"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    donnees_env_id = serializers.IntegerField(source='donnees_environnementales.id', read_only=True)
    
    class Meta:
        model = AnalyseErosion
        fields = [
            'id', 'zone', 'zone_nom', 'donnees_environnementales', 'donnees_env_id',
            'date_analyse', 'horizon_prediction_jours', 'modele_utilise',
            'taux_erosion_predit', 'confiance_prediction',
            'facteur_meteo', 'facteur_marin', 'facteur_topographique', 'facteur_substrat',
            'recommandations', 'niveau_urgence', 'calculs_detaille'
        ]
        read_only_fields = ['id', 'date_analyse']


class LogAPICallSerializer(serializers.ModelSerializer):
    """Serializer pour les logs d'appels API"""
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    
    class Meta:
        model = LogAPICall
        fields = [
            'id', 'service_api', 'endpoint_appele', 'parametres_requete',
            'statut_reponse', 'code_reponse_http', 'temps_reponse_ms',
            'donnees_recues', 'message_erreur', 'timestamp', 'utilisateur', 'utilisateur_nom'
        ]
        read_only_fields = ['id', 'timestamp']


class DonneesConsolideesSerializer(serializers.Serializer):
    """Serializer pour les données consolidées complètes"""
    zone_id = serializers.IntegerField()
    zone_nom = serializers.CharField()
    periode_debut = serializers.DateTimeField()
    periode_fin = serializers.DateTimeField()
    date_collecte = serializers.DateTimeField()
    
    # Données météorologiques
    meteo = serializers.DictField()
    
    # Données topographiques
    topographie = serializers.DictField()
    
    # Données marines
    marines = serializers.DictField()
    
    # Images satellites
    satellite = serializers.DictField()
    
    # Erreurs de collecte
    erreurs = serializers.ListField(child=serializers.CharField())
    
    # Indicateurs calculés
    indice_erosion_potentiel = serializers.FloatField(required=False)
    facteurs_risque = serializers.ListField(child=serializers.CharField(), required=False)
    
    # Recommandations
    recommandations = serializers.ListField(child=serializers.CharField(), required=False)


class PredictionEnrichieSerializer(serializers.Serializer):
    """Serializer pour les prédictions enrichies avec toutes les données"""
    zone_id = serializers.IntegerField()
    zone_nom = serializers.CharField()
    date_prediction = serializers.DateTimeField()
    horizon_jours = serializers.IntegerField()
    
    # Prédiction d'érosion
    taux_erosion_predit = serializers.FloatField()
    confiance_prediction = serializers.FloatField()
    
    # Facteurs d'influence
    facteurs_influence = serializers.DictField()
    
    # Données environnementales utilisées
    donnees_environnementales = DonneesEnvironnementalesSerializer()
    
    # Analyses détaillées
    analyses_detaillees = serializers.ListField(child=serializers.DictField())
    
    # Recommandations
    recommandations = serializers.ListField(child=serializers.CharField())
    niveau_urgence = serializers.CharField()
    
    # Métadonnées
    modele_utilise = serializers.CharField()
    version_modele = serializers.CharField()
    date_calcul = serializers.DateTimeField()


# ============================================================================
# SÉRIALISEURS POUR CAPTEURS ARDUINO NANO ESP32
# ============================================================================

class CapteurArduinoSerializer(serializers.ModelSerializer):
    """Serializer pour les capteurs Arduino"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    est_en_ligne = serializers.ReadOnlyField()
    derniere_mesure = serializers.SerializerMethodField()
    nombre_mesures_total = serializers.SerializerMethodField()
    nombre_mesures_24h = serializers.SerializerMethodField()
    mot_de_passe_wifi_masque = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    
    class Meta:
        model = CapteurArduino
        geo_field = "position"
        id_field = "id"
        fields = [
            'id', 'nom', 'type_capteur', 'zone', 'zone_nom', 'position',
            'adresse_mac', 'adresse_ip', 'ssid_wifi', 'mot_de_passe_wifi_masque',
            'frequence_mesure_secondes', 'precision', 'unite_mesure',
            'valeur_min', 'valeur_max', 'etat', 'date_installation',
            'date_derniere_maintenance', 'date_derniere_communication',
            'version_firmware', 'tension_batterie', 'niveau_signal_wifi',
            'commentaires', 'actif', 'date_creation', 'date_modification',
            'est_en_ligne', 'derniere_mesure', 'nombre_mesures_total', 'nombre_mesures_24h'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification', 'est_en_ligne']
    
    def get_derniere_mesure(self, obj):
        """Retourne la dernière mesure reçue"""
        derniere = obj.derniere_mesure
        if derniere:
            return {
                'valeur': derniere.valeur,
                'unite': derniere.unite,
                'timestamp': derniere.timestamp,
                'qualite_donnee': derniere.qualite_donnee,
                'source_donnee': derniere.source_donnee
            }
        return None
    
    def get_nombre_mesures_total(self, obj):
        """Retourne le nombre total de mesures"""
        return obj.mesures_arduino.count()
    
    def get_nombre_mesures_24h(self, obj):
        """Retourne le nombre de mesures des dernières 24h"""
        from django.utils import timezone
        from datetime import timedelta
        
        hier = timezone.now() - timedelta(hours=24)
        return obj.mesures_arduino.filter(timestamp__gte=hier).count()
    
    def get_mot_de_passe_wifi_masque(self, obj):
        """Masque le mot de passe Wi-Fi pour la sécurité"""
        if obj.mot_de_passe_wifi:
            return "****" if len(obj.mot_de_passe_wifi) > 4 else "**"
        return ""
    
    def get_position(self, obj):
        """Retourne la position sous forme de dictionnaire"""
        if obj.position:
            return {
                'latitude': obj.position.y,
                'longitude': obj.position.x
            }
        return None


class CapteurArduinoDocSerializer(serializers.ModelSerializer):
    """Serializer pour la documentation des capteurs Arduino (sans géométrie)"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    est_en_ligne = serializers.ReadOnlyField()
    derniere_mesure = serializers.SerializerMethodField()
    nombre_mesures_total = serializers.SerializerMethodField()
    mot_de_passe_wifi_masque = serializers.SerializerMethodField()
    
    class Meta:
        model = CapteurArduino
        fields = [
            'id', 'nom', 'type_capteur', 'zone', 'zone_nom',
            'adresse_mac', 'adresse_ip', 'ssid_wifi', 'mot_de_passe_wifi_masque',
            'frequence_mesure_secondes', 'precision', 'unite_mesure',
            'valeur_min', 'valeur_max', 'etat', 'date_installation',
            'date_derniere_maintenance', 'date_derniere_communication',
            'version_firmware', 'tension_batterie', 'niveau_signal_wifi',
            'commentaires', 'actif', 'date_creation', 'date_modification',
            'est_en_ligne', 'derniere_mesure', 'nombre_mesures_total'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification', 'est_en_ligne']
    
    def get_derniere_mesure(self, obj):
        """Retourne la dernière mesure reçue"""
        derniere = obj.derniere_mesure
        if derniere:
            return {
                'valeur': derniere.valeur,
                'unite': derniere.unite,
                'timestamp': derniere.timestamp,
                'qualite_donnee': derniere.qualite_donnee,
                'source_donnee': derniere.source_donnee
            }
        return None
    
    def get_nombre_mesures_total(self, obj):
        """Retourne le nombre total de mesures"""
        return obj.mesures_arduino.count()
    
    def get_mot_de_passe_wifi_masque(self, obj):
        """Masque le mot de passe Wi-Fi pour la sécurité"""
        if obj.mot_de_passe_wifi:
            return "****" if len(obj.mot_de_passe_wifi) > 4 else "**"
        return ""


class MesureArduinoSerializer(serializers.ModelSerializer):
    """Serializer pour les mesures Arduino"""
    capteur_nom = serializers.CharField(source='capteur.nom', read_only=True)
    capteur_type = serializers.CharField(source='capteur.type_capteur', read_only=True)
    zone_nom = serializers.CharField(source='capteur.zone.nom', read_only=True)
    adresse_mac = serializers.CharField(source='capteur.adresse_mac', read_only=True)
    
    class Meta:
        model = MesureArduino
        fields = [
            'id', 'capteur', 'capteur_nom', 'capteur_type', 'zone_nom', 'adresse_mac',
            'valeur', 'unite', 'timestamp', 'timestamp_reception',
            'qualite_donnee', 'source_donnee', 'tension_batterie', 'niveau_signal_wifi',
            'temperature_cpu', 'uptime_secondes', 'est_valide', 'erreur_validation',
            'donnees_brutes', 'commentaires'
        ]
        read_only_fields = ['id', 'timestamp_reception']


class DonneesManquantesSerializer(serializers.ModelSerializer):
    """Serializer pour les données manquantes"""
    capteur_nom = serializers.CharField(source='capteur.nom', read_only=True)
    capteur_type = serializers.CharField(source='capteur.type_capteur', read_only=True)
    zone_nom = serializers.CharField(source='capteur.zone.nom', read_only=True)
    
    class Meta:
        model = DonneesManquantes
        fields = [
            'id', 'capteur', 'capteur_nom', 'capteur_type', 'zone_nom',
            'periode_debut', 'periode_fin', 'duree_manque_minutes',
            'type_completion', 'nombre_valeurs_completees', 'valeurs_completees',
            'date_detection', 'date_completion', 'est_completee', 'qualite_completion',
            'derniere_valeur_connue', 'derniere_timestamp_connu',
            'prochaine_valeur_connue', 'prochain_timestamp_connu', 'commentaires'
        ]
        read_only_fields = ['id', 'date_detection']


class LogCapteurArduinoSerializer(serializers.ModelSerializer):
    """Serializer pour les logs des capteurs Arduino"""
    capteur_nom = serializers.CharField(source='capteur.nom', read_only=True)
    capteur_type = serializers.CharField(source='capteur.type_capteur', read_only=True)
    zone_nom = serializers.CharField(source='capteur.zone.nom', read_only=True)
    
    class Meta:
        model = LogCapteurArduino
        fields = [
            'id', 'capteur', 'capteur_nom', 'capteur_type', 'zone_nom',
            'type_evenement', 'niveau', 'message', 'donnees_contexte',
            'timestamp', 'adresse_ip_source', 'user_agent'
        ]
        read_only_fields = ['id', 'timestamp']


# Serializers pour les données de réception Arduino
class DonneesArduinoReceptionSerializer(serializers.Serializer):
    """Serializer pour recevoir les données des capteurs Arduino"""
    mac_address = serializers.CharField(max_length=17, help_text="Adresse MAC du capteur")
    sensor_type = serializers.CharField(max_length=20, help_text="Type de capteur")
    value = serializers.FloatField(help_text="Valeur mesurée")
    unit = serializers.CharField(max_length=10, help_text="Unité de mesure")
    timestamp = serializers.DateTimeField(help_text="Timestamp de la mesure")
    
    # Données optionnelles
    ip_address = serializers.IPAddressField(required=False, help_text="Adresse IP du capteur")
    battery_voltage = serializers.FloatField(required=False, help_text="Tension batterie (V)")
    wifi_signal = serializers.IntegerField(required=False, help_text="Niveau signal Wi-Fi (dBm)")
    cpu_temperature = serializers.FloatField(required=False, help_text="Température CPU (°C)")
    uptime_seconds = serializers.IntegerField(required=False, help_text="Temps de fonctionnement (s)")
    firmware_version = serializers.CharField(max_length=20, required=False, help_text="Version firmware")
    wifi_ssid = serializers.CharField(max_length=50, required=False, help_text="Nom réseau Wi-Fi")
    
    # Données techniques supplémentaires
    gps_latitude = serializers.FloatField(required=False, help_text="Latitude GPS")
    gps_longitude = serializers.FloatField(required=False, help_text="Longitude GPS")
    gps_altitude = serializers.FloatField(required=False, help_text="Altitude GPS (m)")
    accelerometer_x = serializers.FloatField(required=False, help_text="Accéléromètre X")
    accelerometer_y = serializers.FloatField(required=False, help_text="Accéléromètre Y")
    accelerometer_z = serializers.FloatField(required=False, help_text="Accéléromètre Z")
    
    def validate_mac_address(self, value):
        """Valide le format de l'adresse MAC"""
        import re
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("Format d'adresse MAC invalide")
        return value
    
    def validate_sensor_type(self, value):
        """Valide le type de capteur"""
        types_valides = [choice[0] for choice in CapteurArduino.TYPE_CAPTEUR_CHOICES]
        if value not in types_valides:
            raise serializers.ValidationError(f"Type de capteur invalide. Types valides: {types_valides}")
        return value


class StatistiquesCapteurArduinoSerializer(serializers.Serializer):
    """Serializer pour les statistiques des capteurs Arduino"""
    capteur_id = serializers.IntegerField()
    capteur_nom = serializers.CharField()
    type_capteur = serializers.CharField()
    zone_nom = serializers.CharField()
    
    # État du capteur
    etat = serializers.CharField()
    est_en_ligne = serializers.BooleanField()
    derniere_communication = serializers.DateTimeField()
    
    # Statistiques des mesures
    nombre_mesures_total = serializers.IntegerField()
    nombre_mesures_24h = serializers.IntegerField()
    nombre_mesures_7j = serializers.IntegerField()
    nombre_mesures_30j = serializers.IntegerField()
    
    # Qualité des données
    pourcentage_donnees_valides = serializers.FloatField()
    pourcentage_donnees_reelles = serializers.FloatField()
    pourcentage_donnees_completees = serializers.FloatField()
    
    # Statistiques de valeurs
    valeur_moyenne_24h = serializers.FloatField(required=False)
    valeur_min_24h = serializers.FloatField(required=False)
    valeur_max_24h = serializers.FloatField(required=False)
    
    # Données techniques
    tension_batterie = serializers.FloatField(required=False)
    niveau_signal_wifi = serializers.IntegerField(required=False)
    version_firmware = serializers.CharField()
    
    # Données manquantes
    nombre_periodes_manquantes = serializers.IntegerField()
    duree_totale_manquante_minutes = serializers.IntegerField()


class RapportEtatCapteursSerializer(serializers.Serializer):
    """Serializer pour le rapport d'état des capteurs"""
    total_capteurs = serializers.IntegerField()
    en_ligne = serializers.IntegerField()
    hors_ligne = serializers.IntegerField()
    pourcentage_en_ligne = serializers.FloatField()
    
    # Répartition par état
    etats = serializers.DictField()
    
    # Répartition par type
    types_capteurs = serializers.DictField()
    
    # Alertes
    nombre_alertes_batterie = serializers.IntegerField()
    nombre_alertes_wifi = serializers.IntegerField()
    nombre_alertes_hors_ligne = serializers.IntegerField()
    
    # Métadonnées
    derniere_verification = serializers.DateTimeField()
    prochaine_verification = serializers.DateTimeField()


# ============================================================================
# SÉRIALISEURS POUR ÉVÉNEMENTS EXTERNES ET FUSION DE DONNÉES
# ============================================================================

class EvenementExterneSerializer(serializers.ModelSerializer):
    """Serializer pour les événements externes"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    est_recent = serializers.ReadOnlyField()
    niveau_risque = serializers.ReadOnlyField()
    
    class Meta:
        model = EvenementExterne
        fields = [
            'id', 'type_evenement', 'intensite', 'duree',
            'zone', 'zone_nom', 'date_evenement', 'date_reception',
            'statut', 'source', 'id_source', 'donnees_meteo',
            'latitude', 'longitude', 'zone_erosion', 'niveau_risque',
            'is_simulation', 'is_valide', 'is_traite',
            'commentaires', 'date_creation', 'date_modification',
            'est_recent'
        ]
        read_only_fields = ['id', 'date_reception', 'date_creation', 'date_modification', 'niveau_risque', 'zone_erosion']


class EvenementExterneReceptionSerializer(serializers.Serializer):
    """Serializer pour recevoir les événements externes via API selon le format de votre ami"""
    
    # Champs obligatoires selon le format spécifié
    type = serializers.CharField(max_length=50, help_text="Type d'événement climatique")
    intensite = serializers.FloatField(help_text="Intensité de l'événement")
    duree = serializers.CharField(max_length=20, help_text="Durée de l'événement")
    date = serializers.DateTimeField(help_text="Date/heure ISO 8601")
    statut = serializers.CharField(max_length=20, help_text="Statut de l'événement")
    source = serializers.CharField(max_length=20, help_text="Source de l'événement")
    id = serializers.IntegerField(help_text="ID unique de l'événement")
    
    # Champs optionnels pour géolocalisation
    latitude = serializers.FloatField(required=False, help_text="Latitude")
    longitude = serializers.FloatField(required=False, help_text="Longitude")
    zone_id = serializers.IntegerField(required=False, help_text="ID de la zone concernée")
    
    # Données météo supplémentaires
    donnees_meteo = serializers.JSONField(required=False, default=dict, help_text="Données météo supplémentaires")
    
    def validate_type(self, value):
        """Valide le type d'événement"""
        types_valides = [choice[0] for choice in EvenementExterne.TYPE_CHOICES]
        if value not in types_valides:
            raise serializers.ValidationError(f"Type d'événement invalide. Types valides: {types_valides}")
        return value
    
    def validate_statut(self, value):
        """Valide le statut"""
        statuts_valides = [choice[0] for choice in EvenementExterne.STATUT_CHOICES]
        if value not in statuts_valides:
            raise serializers.ValidationError(f"Statut invalide. Statuts valides: {statuts_valides}")
        return value
    
    def validate_source(self, value):
        """Valide la source"""
        sources_valides = [choice[0] for choice in EvenementExterne.SOURCE_CHOICES]
        if value not in sources_valides:
            raise serializers.ValidationError(f"Source invalide. Sources valides: {sources_valides}")
        return value
    
    def validate_intensite(self, value):
        """Valide l'intensité"""
        if value < 0 or value > 1000:
            raise serializers.ValidationError("Intensité invalide (0-1000)")
        return value
    
    def validate_zone_id(self, value):
        """Valide que la zone existe si fournie"""
        if value is not None:
            try:
                Zone.objects.get(id=value)
            except Zone.DoesNotExist:
                raise serializers.ValidationError("Zone introuvable")
        return value
    
    def create(self, validated_data):
        """Crée un nouvel événement externe"""
        # Extraire les champs optionnels
        zone_id = validated_data.pop('zone_id', None)
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        donnees_meteo = validated_data.pop('donnees_meteo', {})
        
        # Mapper les champs selon le format de votre ami
        evenement_data = {
            'type_evenement': validated_data['type'],
            'intensite': validated_data['intensite'],
            'duree': validated_data['duree'],
            'date_evenement': validated_data['date'],
            'statut': validated_data['statut'],
            'source': validated_data['source'],
            'id_source': validated_data['id'],
            'latitude': latitude,
            'longitude': longitude,
            'donnees_meteo': donnees_meteo,
        }
        
        # Créer l'événement
        evenement = EvenementExterne.objects.create(**evenement_data)
        
        # Associer la zone si fournie
        if zone_id:
            evenement.zone_id = zone_id
            evenement.save()
        
        return evenement


class FusionDonneesSerializer(serializers.ModelSerializer):
    """Serializer pour les fusions de données"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    evenement_externe_nom = serializers.CharField(source='evenement_externe.type_evenement', read_only=True)
    evenement_externe_intensite = serializers.FloatField(source='evenement_externe.intensite', read_only=True)
    
    class Meta:
        model = FusionDonnees
        fields = [
            'id', 'zone', 'zone_nom', 'evenement_externe', 'evenement_externe_nom', 'evenement_externe_intensite',
            'periode_debut', 'periode_fin', 'mesures_arduino_count', 'evenements_externes_count',
            'score_erosion', 'probabilite_erosion', 'facteurs_dominants',
            'statut', 'date_creation', 'date_fin', 'commentaires'
        ]
        read_only_fields = ['id', 'date_creation']


class PredictionEnrichieSerializer(serializers.ModelSerializer):
    """Serializer pour les prédictions enrichies"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    fusion_donnees_id = serializers.IntegerField(source='fusion_donnees.id', read_only=True)
    fusion_score = serializers.FloatField(source='fusion_donnees.score_erosion', read_only=True)
    
    class Meta:
        model = PredictionEnrichie
        fields = [
            'id', 'zone', 'zone_nom', 'fusion_donnees', 'fusion_donnees_id', 'fusion_score',
            'erosion_predite', 'niveau_erosion', 'confiance_pourcentage', 'niveau_confiance',
            'horizon_jours', 'taux_erosion_pred_m_an',
            'facteur_evenements', 'facteur_mesures_arduino', 'facteur_historique',
            'recommandations', 'actions_urgentes', 'modele_utilise', 'parametres_modele',
            'date_prediction', 'commentaires'
        ]
        read_only_fields = ['id', 'date_prediction', 'niveau_confiance']


class AlerteEnrichieSerializer(serializers.ModelSerializer):
    """Serializer pour les alertes enrichies"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    prediction_enrichie_id = serializers.IntegerField(source='prediction_enrichie.id', read_only=True)
    evenement_externe_nom = serializers.CharField(source='evenement_externe.type_evenement', read_only=True)
    utilisateur_resolution_nom = serializers.CharField(source='utilisateur_resolution.get_full_name', read_only=True)
    
    class Meta:
        model = AlerteEnrichie
        fields = [
            'id', 'zone', 'zone_nom', 'prediction_enrichie', 'prediction_enrichie_id',
            'evenement_externe', 'evenement_externe_nom', 'type', 'niveau', 'titre', 'description',
            'est_active', 'est_resolue', 'date_creation', 'date_resolution',
            'actions_requises', 'utilisateur_resolution', 'utilisateur_resolution_nom',
            'donnees_contexte', 'commentaires'
        ]
        read_only_fields = ['id', 'date_creation']


class ArchiveDonneesSerializer(serializers.ModelSerializer):
    """Serializer pour les archives de données"""
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)
    utilisateur_archivage_nom = serializers.CharField(source='utilisateur_archivage.get_full_name', read_only=True)
    
    class Meta:
        model = ArchiveDonnees
        fields = [
            'id', 'type_donnees', 'zone', 'zone_nom', 'periode_debut', 'periode_fin',
            'nombre_elements', 'taille_fichier_mb', 'format_archive', 'date_archivage',
            'utilisateur_archivage', 'utilisateur_archivage_nom', 'chemin_fichier',
            'est_disponible', 'date_suppression', 'description', 'tags'
        ]
        read_only_fields = ['id', 'date_archivage']


# Serializers pour les analyses et statistiques enrichies
class AnalyseFusionSerializer(serializers.Serializer):
    """Serializer pour l'analyse de fusion d'événements et mesures"""
    zone_id = serializers.IntegerField()
    periode_debut = serializers.DateTimeField()
    periode_fin = serializers.DateTimeField()
    
    # Données d'entrée
    evenements_externes = serializers.ListField(child=serializers.DictField())
    mesures_arduino = serializers.ListField(child=serializers.DictField())
    
    # Résultats de l'analyse
    score_erosion = serializers.FloatField()
    probabilite_erosion = serializers.FloatField()
    facteurs_dominants = serializers.ListField(child=serializers.CharField())
    
    # Prédiction générée
    erosion_predite = serializers.BooleanField()
    niveau_erosion = serializers.CharField()
    confiance_pourcentage = serializers.FloatField()
    
    # Recommandations
    recommandations = serializers.ListField(child=serializers.CharField())
    actions_urgentes = serializers.ListField(child=serializers.CharField())
    
    # Métadonnées
    modele_utilise = serializers.CharField()
    date_analyse = serializers.DateTimeField()


class StatistiquesEvenementsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des événements externes"""
    zone_id = serializers.IntegerField()
    zone_nom = serializers.CharField()
    periode_debut = serializers.DateTimeField()
    periode_fin = serializers.DateTimeField()
    
    # Statistiques générales
    nombre_evenements_total = serializers.IntegerField()
    nombre_evenements_par_type = serializers.DictField()
    nombre_evenements_par_intensite = serializers.DictField()
    
    # Événements récents
    nombre_evenements_24h = serializers.IntegerField()
    nombre_evenements_7j = serializers.IntegerField()
    nombre_evenements_30j = serializers.IntegerField()
    
    # Intensité moyenne
    intensite_moyenne = serializers.FloatField()
    intensite_max = serializers.FloatField()
    intensite_min = serializers.FloatField()
    
    # Sources
    sources_uniques = serializers.ListField(child=serializers.CharField())
    nombre_evenements_par_source = serializers.DictField()
    
    # Statut
    nombre_evenements_traites = serializers.IntegerField()
    nombre_evenements_non_traites = serializers.IntegerField()
    nombre_evenements_simulation = serializers.IntegerField()


class RapportFusionSerializer(serializers.Serializer):
    """Serializer pour le rapport de fusion des données"""
    periode_debut = serializers.DateTimeField()
    periode_fin = serializers.DateTimeField()
    
    # Zones analysées
    zones_analysees = serializers.ListField(child=serializers.DictField())
    
    # Statistiques de fusion
    nombre_fusions_total = serializers.IntegerField()
    nombre_fusions_terminees = serializers.IntegerField()
    nombre_fusions_en_cours = serializers.IntegerField()
    nombre_fusions_erreur = serializers.IntegerField()
    
    # Données utilisées
    nombre_evenements_externes_total = serializers.IntegerField()
    nombre_mesures_arduino_total = serializers.IntegerField()
    
    # Prédictions générées
    nombre_predictions_generes = serializers.IntegerField()
    nombre_predictions_erosion_positive = serializers.IntegerField()
    nombre_predictions_erosion_negative = serializers.IntegerField()
    
    # Alertes générées
    nombre_alertes_generes = serializers.IntegerField()
    nombre_alertes_par_niveau = serializers.DictField()
    
    # Qualité des données
    pourcentage_donnees_valides = serializers.FloatField()
    pourcentage_fusions_reussies = serializers.FloatField()
    
    # Métadonnées
    date_generation = serializers.DateTimeField()
    duree_traitement_secondes = serializers.FloatField()
