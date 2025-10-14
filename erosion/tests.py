from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone
from datetime import timedelta
from .models import Zone, Capteur, Mesure, Alerte, HistoriqueErosion

User = get_user_model()


class ZoneModelTest(TestCase):
    """Tests pour le modèle Zone"""
    
    def setUp(self):
        self.zone = Zone.objects.create(
            nom="Zone de test",
            description="Zone pour les tests",
            geometrie=Polygon.from_bbox((-1.2, 44.6, -1.0, 44.8)),
            superficie_km2=50.0,
            niveau_risque='faible'
        )
    
    def test_zone_creation(self):
        """Test de création d'une zone"""
        self.assertEqual(self.zone.nom, "Zone de test")
        self.assertEqual(self.zone.superficie_km2, 50.0)
        self.assertEqual(self.zone.niveau_risque, 'faible')
    
    def test_zone_str(self):
        """Test de la représentation string d'une zone"""
        self.assertEqual(str(self.zone), "Zone de test")


class CapteurModelTest(TestCase):
    """Tests pour le modèle Capteur"""
    
    def setUp(self):
        self.zone = Zone.objects.create(
            nom="Zone de test",
            geometrie=Polygon.from_bbox((-1.2, 44.6, -1.0, 44.8)),
            superficie_km2=50.0
        )
        
        self.capteur = Capteur.objects.create(
            nom="Capteur Test",
            type="temperature",
            zone=self.zone,
            position=Point(-1.1, 44.7),
            precision=0.1,
            unite_mesure="°C"
        )
    
    def test_capteur_creation(self):
        """Test de création d'un capteur"""
        self.assertEqual(self.capteur.nom, "Capteur Test")
        self.assertEqual(self.capteur.type, "temperature")
        self.assertEqual(self.capteur.zone, self.zone)
    
    def test_capteur_str(self):
        """Test de la représentation string d'un capteur"""
        self.assertEqual(str(self.capteur), "Capteur Test (temperature)")


class MesureModelTest(TestCase):
    """Tests pour le modèle Mesure"""
    
    def setUp(self):
        self.zone = Zone.objects.create(
            nom="Zone de test",
            geometrie=Polygon.from_bbox((-1.2, 44.6, -1.0, 44.8)),
            superficie_km2=50.0
        )
        
        self.capteur = Capteur.objects.create(
            nom="Capteur Test",
            type="temperature",
            zone=self.zone,
            position=Point(-1.1, 44.7),
            precision=0.1,
            unite_mesure="°C"
        )
        
        self.mesure = Mesure.objects.create(
            capteur=self.capteur,
            valeur=25.5,
            unite="°C",
            qualite_donnee="bonne"
        )
    
    def test_mesure_creation(self):
        """Test de création d'une mesure"""
        self.assertEqual(self.mesure.capteur, self.capteur)
        self.assertEqual(self.mesure.valeur, 25.5)
        self.assertEqual(self.mesure.unite, "°C")
        self.assertEqual(self.mesure.qualite_donnee, "bonne")
    
    def test_mesure_str(self):
        """Test de la représentation string d'une mesure"""
        expected = f"Capteur Test - 25.5 °C ({self.mesure.timestamp.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(self.mesure), expected)


class AlerteModelTest(TestCase):
    """Tests pour le modèle Alerte"""
    
    def setUp(self):
        self.zone = Zone.objects.create(
            nom="Zone de test",
            geometrie=Polygon.from_bbox((-1.2, 44.6, -1.0, 44.8)),
            superficie_km2=50.0
        )
        
        self.alerte = Alerte.objects.create(
            zone=self.zone,
            type="erosion_acceleree",
            niveau="alerte",
            titre="Test d'alerte",
            description="Description de test"
        )
    
    def test_alerte_creation(self):
        """Test de création d'une alerte"""
        self.assertEqual(self.alerte.zone, self.zone)
        self.assertEqual(self.alerte.type, "erosion_acceleree")
        self.assertEqual(self.alerte.niveau, "alerte")
        self.assertFalse(self.alerte.est_resolue)
    
    def test_alerte_str(self):
        """Test de la représentation string d'une alerte"""
        self.assertEqual(str(self.alerte), "Test d'alerte - alerte")


class HistoriqueErosionModelTest(TestCase):
    """Tests pour le modèle HistoriqueErosion"""
    
    def setUp(self):
        self.zone = Zone.objects.create(
            nom="Zone de test",
            geometrie=Polygon.from_bbox((-1.2, 44.6, -1.0, 44.8)),
            superficie_km2=50.0
        )
        
        self.historique = HistoriqueErosion.objects.create(
            zone=self.zone,
            date_mesure=timezone.now(),
            taux_erosion_m_an=2.5,
            methode_mesure="gps",
            precision_m=0.1
        )
    
    def test_historique_creation(self):
        """Test de création d'un historique d'érosion"""
        self.assertEqual(self.historique.zone, self.zone)
        self.assertEqual(self.historique.taux_erosion_m_an, 2.5)
        self.assertEqual(self.historique.methode_mesure, "gps")
    
    def test_historique_str(self):
        """Test de la représentation string d'un historique"""
        expected = f"Zone de test - {self.historique.date_mesure.strftime('%Y-%m-%d')}"
        self.assertEqual(str(self.historique), expected)