"""
Signaux Django pour l'application erosion
"""

import logging
from django.db.models.signals import post_migrate
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def setup_after_migration(sender, **kwargs):
    """
    Configuration après les migrations
    """
    # Vérifier que c'est notre app
    if sender.name == 'erosion':
        logger.info("🚀 Configuration de l'application erosion après migration...")
        
        try:
            # Ici on peut ajouter des configurations automatiques
            # comme créer des utilisateurs par défaut, des zones, etc.
            logger.info("✅ Configuration terminée avec succès")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la configuration: {e}")