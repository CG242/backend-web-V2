from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Utilisateur, Zone, HistoriqueErosion, Prediction, ModeleML, TendanceLongTerme, 
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


@admin.register(ModeleML)
class ModeleMLAdmin(admin.ModelAdmin):
    list_display = ['nom', 'version', 'type_modele', 'statut', 'precision_score', 'nombre_predictions', 'date_creation']
    list_filter = ['type_modele', 'statut', 'date_creation']
    search_fields = ['nom', 'version', 'commentaires']
    ordering = ['-date_creation']
    readonly_fields = ['date_creation', 'date_derniere_utilisation', 'nombre_predictions']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'version', 'type_modele', 'statut')
        }),
        ('Fichier modèle', {
            'fields': ('chemin_fichier',)
        }),
        ('Performances', {
            'fields': ('precision_score', 'parametres_entrainement', 'features_utilisees')
        }),
        ('Statistiques', {
            'fields': ('nombre_predictions', 'date_derniere_utilisation', 'date_creation')
        }),
        ('Commentaires', {
            'fields': ('commentaires',)
        }),
    )
    
    actions = ['marquer_comme_actif', 'marquer_comme_inactif']
    
    def marquer_comme_actif(self, request, queryset):
        for model in queryset:
            model.marquer_comme_actif()
        self.message_user(request, f"{queryset.count()} modèles marqués comme actifs.")
    marquer_comme_actif.short_description = "Marquer comme actifs"
    
    def marquer_comme_inactif(self, request, queryset):
        queryset.update(statut='inactif')
        self.message_user(request, f"{queryset.count()} modèles marqués comme inactifs.")
    marquer_comme_inactif.short_description = "Marquer comme inactifs"


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['zone', 'modele_ml', 'date_prediction', 'horizon_jours', 'taux_erosion_pred_m_an', 'confiance_pourcentage']
    list_filter = ['zone', 'modele_ml', 'date_prediction']
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
    list_display = ['titre', 'niveau_urgence', 'zone', 'statut', 'source', 'date_creation', 'date_mise_a_jour']
    list_filter = ['niveau_urgence', 'statut', 'source', 'date_creation']
    search_fields = ['titre', 'description', 'zone', 'source']
    ordering = ['-date_creation']
    readonly_fields = ['date_creation', 'date_mise_a_jour']


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
    list_display = ['type_evenement', 'intensite', 'duree', 'zone', 'date_evenement', 'source', 'niveau_risque', 'date_reception']
    list_filter = ['type_evenement', 'niveau_risque', 'statut', 'source', 'is_simulation', 'zone', 'date_evenement']
    search_fields = ['type_evenement', 'zone__nom', 'source', 'id_source']
    ordering = ['-date_evenement']
    readonly_fields = ['date_evenement', 'date_creation', 'date_modification', 'niveau_risque', 'zone_erosion']
    date_hierarchy = 'date_evenement'
    
    fieldsets = (
        ('Événement', {
            'fields': ('type_evenement', 'intensite', 'duree', 'date_evenement', 'statut')
        }),
        ('Risque d\'érosion (calculé automatiquement)', {
            'fields': ('niveau_risque', 'zone_erosion'),
            'classes': ('collapse',)
        }),
        ('Localisation', {
            'fields': ('zone', 'latitude', 'longitude')
        }),
        ('Source', {
            'fields': ('source', 'id_source', 'donnees_meteo', 'is_simulation')
        }),
        ('Métadonnées', {
            'fields': ('commentaires', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['marquer_comme_valide', 'marquer_comme_simulation', 'purger_simulations']
    
    def marquer_comme_valide(self, request, queryset):
        queryset.update(is_simulation=False, is_valide=True)
        self.message_user(request, f"{queryset.count()} événements marqués comme valides (données réelles).")
    marquer_comme_valide.short_description = "✅ Marquer comme données réelles"
    
    def marquer_comme_simulation(self, request, queryset):
        queryset.update(is_simulation=True)
        self.message_user(request, f"{queryset.count()} événements marqués comme simulations (tests internes).")
    marquer_comme_simulation.short_description = "🔧 Marquer comme simulation/test"
    
    def purger_simulations(self, request, queryset):
        count = queryset.filter(is_simulation=True).count()
        queryset.filter(is_simulation=True).delete()
        self.message_user(request, f"{count} événements de simulation supprimés.")
    purger_simulations.short_description = "🗑️ Supprimer les simulations"


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
    list_display = ['titre', 'zone', 'type', 'niveau', 'est_active', 'est_resolue', 'date_creation', 'envoyer_alerte']
    list_filter = ['type', 'niveau', 'est_active', 'est_resolue', 'zone', 'date_creation']
    search_fields = ['titre', 'description', 'zone__nom']
    ordering = ['-date_creation']
    readonly_fields = ['date_creation']
    date_hierarchy = 'date_creation'
    
    def envoyer_alerte(self, obj):
        """Bouton pour envoyer l'alerte au système externe"""
        if obj.est_active and not obj.est_resolue:
            return format_html(
                '<a class="button" href="javascript:void(0)" '
                'onclick="envoyerAlerte({})" style="background-color: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">'
                '📤 Envoyer'
                '</a>',
                obj.id
            )
        return "N/A"
    envoyer_alerte.short_description = "Envoyer"
    
    class Media:
        js = ('admin/js/alerte_envoi.js',)


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