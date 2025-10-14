from django.contrib import admin
from .models import (
    Utilisateur, Zone, HistoriqueErosion, Prediction, TendanceLongTerme, 
    Alerte, EvenementClimatique, JournalAction,
    CapteurArduino, MesureArduino, DonneesManquantes, LogCapteurArduino,
    EvenementExterne, FusionDonnees, PredictionEnrichie, AlerteEnrichie, ArchiveDonnees
)


# ============================================================================
# ADMINISTRATION DES MODÈLES PRINCIPAUX (FONCTIONNELS)
# ============================================================================

@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['nom', 'superficie_km2', 'niveau_risque', 'date_creation']
    list_filter = ['niveau_risque', 'date_creation']
    search_fields = ['nom', 'description']
    ordering = ['nom']


@admin.register(HistoriqueErosion)
class HistoriqueErosionAdmin(admin.ModelAdmin):
    list_display = ['zone', 'date_mesure', 'taux_erosion_m_an', 'methode_mesure', 'utilisateur']
    list_filter = ['zone', 'methode_mesure', 'date_mesure']
    search_fields = ['zone__nom', 'commentaires']
    ordering = ['-date_mesure']


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['zone', 'date_prediction', 'horizon_jours', 'taux_erosion_pred_m_an', 'confiance_pourcentage']
    list_filter = ['zone', 'modele_utilise', 'date_prediction']
    search_fields = ['zone__nom', 'commentaires']
    ordering = ['-date_prediction']


@admin.register(TendanceLongTerme)
class TendanceLongTermeAdmin(admin.ModelAdmin):
    list_display = ['zone', 'periode_debut', 'periode_fin', 'taux_erosion_moyen_m_an', 'tendance']
    list_filter = ['zone', 'tendance', 'date_analyse']
    search_fields = ['zone__nom']
    ordering = ['-date_analyse']


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ['titre', 'zone', 'type', 'niveau', 'est_resolue', 'date_creation']
    list_filter = ['type', 'niveau', 'est_resolue', 'zone', 'date_creation']
    search_fields = ['titre', 'description', 'zone__nom']
    ordering = ['-date_creation']


@admin.register(EvenementClimatique)
class EvenementClimatiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type', 'intensite', 'date_debut', 'date_fin']
    list_filter = ['type', 'intensite', 'date_debut']
    search_fields = ['nom', 'description']
    ordering = ['-date_debut']
    filter_horizontal = ['zones_impactees']


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'action', 'objet_type', 'timestamp']
    list_filter = ['action', 'objet_type', 'timestamp']
    search_fields = ['utilisateur__username', 'description']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp']


# ============================================================================
# ADMIN POUR CAPTEURS ARDUINO (FONCTIONNELS)
# ============================================================================

@admin.register(CapteurArduino)
class CapteurArduinoAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_capteur', 'adresse_mac', 'adresse_ip', 'etat', 'zone', 'date_derniere_communication']
    list_filter = ['type_capteur', 'etat', 'zone', 'date_derniere_communication']
    search_fields = ['nom', 'adresse_mac', 'adresse_ip', 'commentaires']
    ordering = ['-date_derniere_communication']
    readonly_fields = ['date_derniere_communication']
    date_hierarchy = 'date_derniere_communication'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'type_capteur', 'zone', 'etat')
        }),
        ('Configuration réseau', {
            'fields': ('adresse_mac', 'adresse_ip', 'ssid_wifi')
        }),
        ('Paramètres techniques', {
            'fields': ('precision', 'unite_mesure', 'frequence_mesure_secondes', 'valeur_min', 'valeur_max')
        }),
        ('Statut', {
            'fields': ('date_derniere_communication', 'actif', 'tension_batterie', 'niveau_signal_wifi')
        }),
        ('Commentaires', {
            'fields': ('commentaires',)
        }),
    )


@admin.register(MesureArduino)
class MesureArduinoAdmin(admin.ModelAdmin):
    list_display = ['capteur', 'valeur', 'unite', 'timestamp', 'qualite_donnee', 'est_valide']
    list_filter = ['capteur__type_capteur', 'qualite_donnee', 'est_valide', 'source_donnee', 'timestamp']
    search_fields = ['capteur__nom', 'capteur__adresse_mac', 'commentaires']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp', 'donnees_brutes']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Mesure', {
            'fields': ('capteur', 'valeur', 'unite', 'timestamp')
        }),
        ('Qualité', {
            'fields': ('qualite_donnee', 'est_valide', 'source_donnee')
        }),
        ('Données techniques', {
            'fields': ('tension_batterie', 'niveau_signal_wifi', 'temperature_cpu', 'uptime_secondes')
        }),
        ('Données brutes', {
            'fields': ('donnees_brutes', 'commentaires')
        }),
    )


@admin.register(DonneesManquantes)
class DonneesManquantesAdmin(admin.ModelAdmin):
    list_display = ['capteur', 'periode_debut', 'periode_fin', 'duree_manque_minutes', 'type_completion']
    list_filter = ['type_completion', 'periode_debut', 'est_completee']
    search_fields = ['capteur__nom', 'capteur__adresse_mac']
    ordering = ['-periode_debut']
    readonly_fields = ['periode_debut', 'periode_fin', 'duree_manque_minutes', 'date_detection']
    date_hierarchy = 'periode_debut'


@admin.register(LogCapteurArduino)
class LogCapteurArduinoAdmin(admin.ModelAdmin):
    list_display = ['capteur', 'type_evenement', 'niveau', 'timestamp', 'message']
    list_filter = ['type_evenement', 'niveau', 'timestamp']
    search_fields = ['capteur__nom', 'capteur__adresse_mac', 'message']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False  # Les logs sont créés automatiquement
    
    def has_change_permission(self, request, obj=None):
        return False  # Les logs ne doivent pas être modifiés


# ============================================================================
# ADMIN POUR ÉVÉNEMENTS EXTERNES ET FUSION DE DONNÉES
# ============================================================================

@admin.register(EvenementExterne)
class EvenementExterneAdmin(admin.ModelAdmin):
    list_display = ['type_evenement', 'intensite', 'zone', 'date_evenement', 'source', 'is_simulation']
    list_filter = ['type_evenement', 'intensite', 'is_simulation', 'zone', 'date_evenement']
    search_fields = ['type_evenement', 'description', 'zone__nom', 'source']
    ordering = ['-date_evenement']
    readonly_fields = ['date_evenement']
    date_hierarchy = 'date_evenement'
    
    fieldsets = (
        ('Événement', {
            'fields': ('type_evenement', 'intensite', 'description', 'date_evenement')
        }),
        ('Localisation', {
            'fields': ('zone',)
        }),
        ('Source', {
            'fields': ('source', 'metadata', 'is_simulation')
        }),
    )
    
    actions = ['marquer_comme_valide', 'marquer_comme_invalide', 'purger_simulations']
    
    def marquer_comme_valide(self, request, queryset):
        queryset.update(is_simulation=False)
        self.message_user(request, f"{queryset.count()} événements marqués comme valides.")
    marquer_comme_valide.short_description = "Marquer comme valides"
    
    def marquer_comme_invalide(self, request, queryset):
        queryset.update(is_simulation=True)
        self.message_user(request, f"{queryset.count()} événements marqués comme invalides.")
    marquer_comme_invalide.short_description = "Marquer comme invalides"
    
    def purger_simulations(self, request, queryset):
        count = queryset.filter(is_simulation=True).count()
        queryset.filter(is_simulation=True).delete()
        self.message_user(request, f"{count} événements de simulation supprimés.")
    purger_simulations.short_description = "Purger les simulations"


@admin.register(FusionDonnees)
class FusionDonneesAdmin(admin.ModelAdmin):
    list_display = ['zone', 'evenement_externe', 'periode_debut', 'periode_fin', 'mesures_arduino_count', 'evenements_externes_count']
    list_filter = ['statut', 'zone', 'periode_debut']
    search_fields = ['zone__nom', 'evenement_externe__type_evenement']
    ordering = ['-periode_debut']
    readonly_fields = ['periode_debut', 'periode_fin', 'mesures_arduino_count', 'evenements_externes_count']
    date_hierarchy = 'periode_debut'


@admin.register(PredictionEnrichie)
class PredictionEnrichieAdmin(admin.ModelAdmin):
    list_display = ['zone', 'date_prediction', 'horizon_jours', 'taux_erosion_pred_m_an', 'confiance_pourcentage']
    list_filter = ['zone', 'modele_utilise', 'date_prediction']
    search_fields = ['zone__nom', 'commentaires']
    ordering = ['-date_prediction']
    readonly_fields = ['date_prediction']
    date_hierarchy = 'date_prediction'


@admin.register(AlerteEnrichie)
class AlerteEnrichieAdmin(admin.ModelAdmin):
    list_display = ['titre', 'zone', 'type', 'niveau', 'est_active', 'est_resolue', 'date_creation']
    list_filter = ['type', 'niveau', 'est_active', 'est_resolue', 'zone', 'date_creation']
    search_fields = ['titre', 'description', 'zone__nom']
    ordering = ['-date_creation']
    readonly_fields = ['date_creation']
    date_hierarchy = 'date_creation'


@admin.register(ArchiveDonnees)
class ArchiveDonneesAdmin(admin.ModelAdmin):
    list_display = ['type_donnees', 'zone', 'periode_debut', 'periode_fin', 'nombre_elements', 'taille_fichier_mb']
    list_filter = ['type_donnees', 'zone', 'date_archivage']
    search_fields = ['zone__nom', 'chemin_fichier']
    ordering = ['-date_archivage']
    readonly_fields = ['date_archivage', 'nombre_elements', 'taille_fichier_mb']
    date_hierarchy = 'date_archivage'


# ============================================================================
# MODÈLES SUPPRIMÉS DE L'ADMIN (CAPTEURS SIMPLES)
# ============================================================================

# Les modèles suivants sont commentés car vous utilisez seulement les capteurs Arduino :
# - Capteur, Mesure (capteurs simples)
# - CleAPI, DonneesCartographiques, DonneesEnvironnementales, AnalyseErosion, LogAPICall