from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    UtilisateurViewSet, ZoneViewSet, HistoriqueErosionViewSet,
    PredictionViewSet, TendanceLongTermeViewSet, AlerteViewSet, 
    EvenementClimatiqueViewSet, JournalActionViewSet
)
from .views_evenements import (
    EvenementExterneViewSet, FusionDonneesViewSet, PredictionEnrichieViewSet,
    AlerteEnrichieViewSet, ArchiveDonneesViewSet
)
from .views_arduino import (
    CapteurArduinoViewSet, MesureArduinoViewSet, DonneesManquantesViewSet,
    LogCapteurArduinoViewSet, recevoir_donnees_arduino, recevoir_donnees_arduino_batch,
    rapport_etat_capteurs, detecter_et_completer_donnees_manquantes
)

# Configuration du router DRF - Routes principales uniquement
router = DefaultRouter()
router.register(r'utilisateurs', UtilisateurViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'historique-erosion', HistoriqueErosionViewSet)
router.register(r'predictions', PredictionViewSet)
router.register(r'tendances', TendanceLongTermeViewSet)
router.register(r'alertes', AlerteViewSet)
router.register(r'evenements-climatiques', EvenementClimatiqueViewSet)
router.register(r'logs', JournalActionViewSet)

# Routes pour les capteurs Arduino (fonctionnelles)
router.register(r'capteurs-arduino', CapteurArduinoViewSet)
router.register(r'mesures-arduino', MesureArduinoViewSet)
router.register(r'donnees-manquantes', DonneesManquantesViewSet)
router.register(r'logs-capteurs-arduino', LogCapteurArduinoViewSet)

# Routes pour les événements externes et fusion de données
router.register(r'evenements-externes', EvenementExterneViewSet)
router.register(r'fusions-donnees', FusionDonneesViewSet)
router.register(r'predictions-enrichies', PredictionEnrichieViewSet)
router.register(r'alertes-enrichies', AlerteEnrichieViewSet)
router.register(r'archives-donnees', ArchiveDonneesViewSet)

app_name = 'erosion'

urlpatterns = [
    # URLs de l'API REST
    path('api/', include(router.urls)),
    
    # URLs d'authentification JWT
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # URLs pour la réception des données Arduino
    path('api/arduino/recevoir-donnees/', recevoir_donnees_arduino, name='recevoir_donnees_arduino'),
    path('api/arduino/recevoir-donnees-batch/', recevoir_donnees_arduino_batch, name='recevoir_donnees_arduino_batch'),
    path('api/arduino/rapport-etat/', rapport_etat_capteurs, name='rapport_etat_capteurs'),
    path('api/arduino/completer-donnees-manquantes/', detecter_et_completer_donnees_manquantes, name='completer_donnees_manquantes'),
]

# ============================================================================
# ROUTES SUPPRIMÉES (CAPTEURS SIMPLES)
# ============================================================================

# Les routes suivantes sont commentées car vous utilisez seulement les capteurs Arduino :
# - CapteurViewSet, MesureViewSet (capteurs simples)
# - Routes enrichies : CleAPIViewSet, DonneesCartographiquesViewSet, etc.
# - Routes événements : EvenementExterneViewSet, FusionDonneesViewSet, etc.