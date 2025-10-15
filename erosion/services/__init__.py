# Services pour l'analyse et la fusion de données

# Imports des services ML
from .analyse_fusion_service import AnalyseFusionService, ArchiveService

# Imports des services ML depuis le fichier services.py principal
try:
    from ..services import MLPredictionService, MLTrainingService
except ImportError:
    # Fallback si les services ne sont pas encore disponibles
    pass