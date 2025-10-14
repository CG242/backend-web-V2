"""
Système de notifications pour la détection des capteurs Arduino
- Notifications en temps réel via WebSocket
- Alertes par email
- Notifications push
- Logs détaillés
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    get_channel_layer = None
    async_to_sync = None

from .models import CapteurArduino, LogCapteurArduino, Utilisateur

logger = logging.getLogger(__name__)


class CapteurNotificationService:
    """Service de notifications pour les capteurs Arduino"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer() if CHANNELS_AVAILABLE else None
    
    def capteur_detecte(self, capteur: CapteurArduino, adresse_ip: str = None):
        """
        Notifie qu'un capteur a été détecté/connexion établie
        """
        try:
            # Mettre à jour l'état du capteur
            capteur.etat = 'actif'
            capteur.date_derniere_communication = timezone.now()
            if adresse_ip:
                capteur.adresse_ip = adresse_ip
            capteur.save()
            
            # Créer un log d'événement
            LogCapteurArduino.objects.create(
                capteur=capteur,
                type_evenement='connexion',
                niveau='info',
                message=f'Capteur détecté et connecté - IP: {adresse_ip or "Inconnue"}',
                donnees_contexte={
                    'adresse_ip': adresse_ip,
                    'timestamp_connexion': timezone.now().isoformat(),
                    'etat_precedent': 'inconnu'
                },
                adresse_ip_source=adresse_ip
            )
            
            # Envoyer les notifications
            self._envoyer_notification_websocket(capteur, 'capteur_detecte')
            self._envoyer_notification_email(capteur, 'detection')
            self._envoyer_notification_dashboard(capteur, 'detection')
            
            logger.info(f"Capteur détecté: {capteur.nom} ({capteur.adresse_mac})")
            
        except Exception as e:
            logger.error(f"Erreur lors de la notification de détection: {e}")
    
    def capteur_deconnecte(self, capteur: CapteurArduino, raison: str = "Déconnexion inattendue"):
        """
        Notifie qu'un capteur s'est déconnecté
        """
        try:
            # Mettre à jour l'état du capteur
            capteur.etat = 'hors_ligne'
            capteur.save()
            
            # Créer un log d'événement
            LogCapteurArduino.objects.create(
                capteur=capteur,
                type_evenement='deconnexion',
                niveau='attention',
                message=f'Capteur déconnecté - Raison: {raison}',
                donnees_contexte={
                    'raison_deconnexion': raison,
                    'timestamp_deconnexion': timezone.now().isoformat(),
                    'derniere_communication': capteur.date_derniere_communication.isoformat() if capteur.date_derniere_communication else None
                }
            )
            
            # Envoyer les notifications
            self._envoyer_notification_websocket(capteur, 'capteur_deconnecte')
            self._envoyer_notification_email(capteur, 'deconnexion')
            self._envoyer_notification_dashboard(capteur, 'deconnexion')
            
            logger.warning(f"Capteur déconnecté: {capteur.nom} ({capteur.adresse_mac}) - {raison}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la notification de déconnexion: {e}")
    
    def capteur_nouveau(self, capteur: CapteurArduino, adresse_ip: str = None):
        """
        Notifie qu'un nouveau capteur a été découvert
        """
        try:
            # Créer un log d'événement
            LogCapteurArduino.objects.create(
                capteur=capteur,
                type_evenement='nouveau_capteur',
                niveau='info',
                message=f'Nouveau capteur découvert - MAC: {capteur.adresse_mac}',
                donnees_contexte={
                    'adresse_mac': capteur.adresse_mac,
                    'adresse_ip': adresse_ip,
                    'type_capteur': capteur.type_capteur,
                    'timestamp_decouverte': timezone.now().isoformat()
                },
                adresse_ip_source=adresse_ip
            )
            
            # Envoyer les notifications
            self._envoyer_notification_websocket(capteur, 'nouveau_capteur')
            self._envoyer_notification_email(capteur, 'nouveau')
            self._envoyer_notification_dashboard(capteur, 'nouveau')
            
            logger.info(f"Nouveau capteur découvert: {capteur.nom} ({capteur.adresse_mac})")
            
        except Exception as e:
            logger.error(f"Erreur lors de la notification nouveau capteur: {e}")
    
    def capteur_alerte(self, capteur: CapteurArduino, type_alerte: str, message: str, niveau: str = 'attention'):
        """
        Envoie une alerte pour un capteur
        """
        try:
            # Créer un log d'événement
            LogCapteurArduino.objects.create(
                capteur=capteur,
                type_evenement='alerte',
                niveau=niveau,
                message=message,
                donnees_contexte={
                    'type_alerte': type_alerte,
                    'timestamp_alerte': timezone.now().isoformat()
                }
            )
            
            # Envoyer les notifications
            self._envoyer_notification_websocket(capteur, 'alerte', {
                'type_alerte': type_alerte,
                'message': message,
                'niveau': niveau
            })
            self._envoyer_notification_email(capteur, 'alerte', {
                'type_alerte': type_alerte,
                'message': message
            })
            self._envoyer_notification_dashboard(capteur, 'alerte', {
                'type_alerte': type_alerte,
                'message': message,
                'niveau': niveau
            })
            
            logger.warning(f"Alerte capteur {capteur.nom}: {message}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi d'alerte: {e}")
    
    def _envoyer_notification_websocket(self, capteur: CapteurArduino, type_notification: str, donnees_extra: Dict = None):
        """
        Envoie une notification via WebSocket en temps réel
        """
        try:
            if not CHANNELS_AVAILABLE or not self.channel_layer:
                logger.info("WebSocket non disponible - notification ignorée")
                return
            
            # Données de base
            notification_data = {
                'type': 'capteur_notification',
                'capteur_id': capteur.id,
                'capteur_nom': capteur.nom,
                'capteur_mac': capteur.adresse_mac,
                'type_capteur': capteur.type_capteur,
                'zone_nom': capteur.zone.nom,
                'type_notification': type_notification,
                'timestamp': timezone.now().isoformat(),
                'etat_capteur': capteur.etat
            }
            
            # Ajouter les données supplémentaires
            if donnees_extra:
                notification_data.update(donnees_extra)
            
            # Envoyer à tous les clients connectés
            async_to_sync(self.channel_layer.group_send)(
                'capteurs_notifications',
                {
                    'type': 'send_notification',
                    'message': notification_data
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur WebSocket notification: {e}")
    
    def _envoyer_notification_email(self, capteur: CapteurArduino, type_notification: str, donnees_extra: Dict = None):
        """
        Envoie une notification par email
        """
        try:
            # Récupérer les utilisateurs à notifier
            utilisateurs = Utilisateur.objects.filter(
                Q(role__in=['admin', 'scientifique', 'technicien']) &
                Q(is_active=True)
            )
            
            if not utilisateurs.exists():
                return
            
            # Préparer le sujet et le message
            sujets = {
                'detection': f'✅ Capteur détecté: {capteur.nom}',
                'deconnexion': f'⚠️ Capteur déconnecté: {capteur.nom}',
                'nouveau': f'🆕 Nouveau capteur découvert: {capteur.nom}',
                'alerte': f'🚨 Alerte capteur: {capteur.nom}'
            }
            
            sujet = sujets.get(type_notification, f'Notification capteur: {capteur.nom}')
            
            # Construire le message
            message = self._construire_message_email(capteur, type_notification, donnees_extra)
            
            # Envoyer l'email
            emails = [user.email for user in utilisateurs if user.email]
            if emails:
                send_mail(
                    sujet,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    emails,
                    fail_silently=True
                )
                
        except Exception as e:
            logger.error(f"Erreur email notification: {e}")
    
    def _envoyer_notification_dashboard(self, capteur: CapteurArduino, type_notification: str, donnees_extra: Dict = None):
        """
        Envoie une notification pour le dashboard
        """
        try:
            # Ici, on pourrait intégrer avec des services comme:
            # - Slack
            # - Discord
            # - Teams
            # - Push notifications mobiles
            
            # Pour l'instant, on log juste
            logger.info(f"Dashboard notification: {type_notification} pour {capteur.nom}")
            
        except Exception as e:
            logger.error(f"Erreur dashboard notification: {e}")
    
    def _construire_message_email(self, capteur: CapteurArduino, type_notification: str, donnees_extra: Dict = None) -> str:
        """
        Construit le message email
        """
        message = f"""
Système de Surveillance d'Érosion Côtière
==========================================

Capteur: {capteur.nom}
Type: {capteur.get_type_capteur_display()}
Zone: {capteur.zone.nom}
Adresse MAC: {capteur.adresse_mac}
Adresse IP: {capteur.adresse_ip or 'Non assignée'}

"""
        
        if type_notification == 'detection':
            message += f"""
✅ CAPTEUR DÉTECTÉ ET CONNECTÉ

Le capteur {capteur.nom} s'est connecté au système.
Dernière communication: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

État: {capteur.get_etat_display()}
"""
        
        elif type_notification == 'deconnexion':
            message += f"""
⚠️ CAPTEUR DÉCONNECTÉ

Le capteur {capteur.nom} s'est déconnecté du système.
Dernière communication: {capteur.date_derniere_communication.strftime('%Y-%m-%d %H:%M:%S') if capteur.date_derniere_communication else 'Inconnue'}

Raison: {donnees_extra.get('raison_deconnexion', 'Inconnue') if donnees_extra else 'Inconnue'}
"""
        
        elif type_notification == 'nouveau':
            message += f"""
🆕 NOUVEAU CAPTEUR DÉCOUVERT

Un nouveau capteur a été découvert:
- Nom: {capteur.nom}
- Type: {capteur.get_type_capteur_display()}
- Adresse MAC: {capteur.adresse_mac}
- Zone: {capteur.zone.nom}

Ce capteur a été automatiquement ajouté au système.
"""
        
        elif type_notification == 'alerte':
            message += f"""
🚨 ALERTE CAPTEUR

Alerte pour le capteur {capteur.nom}:
Type: {donnees_extra.get('type_alerte', 'Inconnu') if donnees_extra else 'Inconnu'}
Message: {donnees_extra.get('message', 'Aucun message') if donnees_extra else 'Aucun message'}

Veuillez vérifier l'état du capteur.
"""
        
        message += f"""

---
Système de Surveillance d'Érosion Côtière
Généré automatiquement le {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return message


class CapteurDetectionService:
    """Service de détection automatique des capteurs"""
    
    @staticmethod
    def detecter_capteurs_connectes():
        """
        Détecte tous les capteurs actuellement connectés
        """
        try:
            maintenant = timezone.now()
            timeout = timedelta(minutes=5)  # 5 minutes de timeout
            
            capteurs_connectes = CapteurArduino.objects.filter(
                Q(date_derniere_communication__gte=maintenant - timeout) |
                Q(etat='actif')
            )
            
            return capteurs_connectes
            
        except Exception as e:
            logger.error(f"Erreur détection capteurs connectés: {e}")
            return CapteurArduino.objects.none()
    
    @staticmethod
    def detecter_capteurs_deconnectes():
        """
        Détecte tous les capteurs déconnectés
        """
        try:
            maintenant = timezone.now()
            timeout = timedelta(minutes=30)  # 30 minutes de timeout
            
            capteurs_deconnectes = CapteurArduino.objects.filter(
                Q(date_derniere_communication__lt=maintenant - timeout) |
                Q(date_derniere_communication__isnull=True)
            ).exclude(etat='hors_ligne')
            
            return capteurs_deconnectes
            
        except Exception as e:
            logger.error(f"Erreur détection capteurs déconnectés: {e}")
            return CapteurArduino.objects.none()
    
    @staticmethod
    def verifier_etat_capteurs():
        """
        Vérifie l'état de tous les capteurs et envoie les notifications
        """
        try:
            notification_service = CapteurNotificationService()
            
            # Détecter les capteurs déconnectés
            capteurs_deconnectes = CapteurDetectionService.detecter_capteurs_deconnectes()
            
            for capteur in capteurs_deconnectes:
                notification_service.capteur_deconnecte(
                    capteur, 
                    "Pas de communication depuis plus de 30 minutes"
                )
            
            # Détecter les capteurs avec batterie faible
            capteurs_batterie_faible = CapteurArduino.objects.filter(
                tension_batterie__lt=3.2,
                etat__in=['actif', 'inactif']
            )
            
            for capteur in capteurs_batterie_faible:
                notification_service.capteur_alerte(
                    capteur,
                    'batterie_faible',
                    f'Batterie faible: {capteur.tension_batterie}V',
                    'attention'
                )
            
            # Détecter les capteurs avec signal Wi-Fi faible
            capteurs_signal_faible = CapteurArduino.objects.filter(
                niveau_signal_wifi__lt=-80,
                etat__in=['actif', 'inactif']
            )
            
            for capteur in capteurs_signal_faible:
                notification_service.capteur_alerte(
                    capteur,
                    'signal_wifi_faible',
                    f'Signal Wi-Fi faible: {capteur.niveau_signal_wifi}dBm',
                    'attention'
                )
            
            logger.info(f"Vérification état capteurs terminée")
            
        except Exception as e:
            logger.error(f"Erreur vérification état capteurs: {e}")


# Fonctions utilitaires pour les vues
def notifier_capteur_detecte(capteur: CapteurArduino, adresse_ip: str = None):
    """Fonction utilitaire pour notifier la détection d'un capteur"""
    service = CapteurNotificationService()
    service.capteur_detecte(capteur, adresse_ip)

def notifier_capteur_nouveau(capteur: CapteurArduino, adresse_ip: str = None):
    """Fonction utilitaire pour notifier un nouveau capteur"""
    service = CapteurNotificationService()
    service.capteur_nouveau(capteur, adresse_ip)

def notifier_capteur_alerte(capteur: CapteurArduino, type_alerte: str, message: str, niveau: str = 'attention'):
    """Fonction utilitaire pour notifier une alerte"""
    service = CapteurNotificationService()
    service.capteur_alerte(capteur, type_alerte, message, niveau)
