# 🌊 API Surveillance Érosion Côtière

## 📋 Description

Système de surveillance et de prédiction de l'érosion côtière utilisant Django REST Framework avec PostgreSQL/PostGIS pour la gestion des données géospatiales. Cette API permet de surveiller les zones côtières, collecter des données de capteurs environnementaux, et générer des prédictions d'érosion.

## 🏗️ Architecture

### Technologies Utilisées
- **Backend**: Django 5.2.7 + Django REST Framework
- **Base de données**: PostgreSQL avec PostGIS (installation locale)
- **Géospatial**: GDAL via conda-forge
- **Authentification**: JWT (SimpleJWT)
- **Tâches asynchrones**: Celery + Redis
- **Documentation**: Swagger/OpenAPI (drf-spectacular)
- **Format géospatial**: GeoJSON
- **Architecture**: Installation locale (pas de Docker)

### Structure du Projet
```
backend/
├── backend/                 # Configuration Django
│   ├── settings.py         # Configuration principale
│   ├── urls.py            # URLs principales
│   ├── celery.py          # Configuration Celery
│   └── celery_beat_schedule.py  # Tâches périodiques
├── erosion/                # Application principale
│   ├── models.py          # Modèles de données
│   ├── serializers.py     # Sérialiseurs DRF
│   ├── views.py           # Vues API
│   ├── urls.py            # URLs de l'API
│   ├── filters.py         # Filtres Django
│   ├── permissions.py     # Permissions personnalisées
│   ├── signals.py         # Signaux Django
│   ├── tasks.py           # Tâches Celery
│   └── management/commands/  # Commandes Django
├── scripts/               # Scripts utilitaires
│   └── simulate_data.py  # Simulation de données
├── requirements.txt       # Dépendances Python
├── env.example           # Variables d'environnement
└── README.md             # Documentation
```

## 🚀 Installation et Configuration

### Prérequis
- Python 3.12+
- PostgreSQL avec PostGIS installé localement
- Redis (pour Celery)
- Miniconda (pour GDAL sur Windows)

### 1. Installation des Dépendances

```bash
# Cloner le projet
git clone <repository-url>
cd backend

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances Python
pip install -r requirements.txt

# Installer GDAL via conda (Windows)
conda install -c conda-forge gdal
```

### 2. Configuration de la Base de Données PostgreSQL

```bash
# Créer la base de données PostgreSQL (Windows)
# Ouvrir pgAdmin ou utiliser psql en ligne de commande
createdb -U postgres erosion_db
psql -U postgres -d erosion_db -c "CREATE EXTENSION postgis;"

# Ou via pgAdmin :
# 1. Créer une nouvelle base de données nommée 'erosion_db'
# 2. Exécuter la requête : CREATE EXTENSION postgis;
```

### 3. Configuration des Variables d'Environnement

```bash
# Copier le fichier d'exemple
cp env.example .env

# Éditer les variables selon votre configuration
nano .env
```

Variables importantes :
```env
DATABASE_NAME=erosion_db
DATABASE_USER=postgres
DATABASE_PASSWORD=votre_mot_de_passe
DATABASE_HOST=localhost
DATABASE_PORT=5432
SECRET_KEY=votre_clé_secrète
DEBUG=True
```

### 4. Initialisation du Projet

```bash
# Appliquer les migrations
python manage.py migrate

# Créer un superutilisateur
python manage.py createsuperuser

# Générer des données de test
python manage.py simulate_data
```

## 🔧 Démarrage du Serveur

### Développement Local
```bash
# Serveur Django
python manage.py runserver

# Celery Worker (terminal séparé)
celery -A backend worker --loglevel=info

# Celery Beat (terminal séparé)
celery -A backend beat --loglevel=info
```

### Production
Pour la production, utilisez un serveur WSGI comme Gunicorn :
```bash
pip install gunicorn
gunicorn backend.wsgi:application --bind 0.0.0.0:8000
```

## 📡 API Endpoints

### Authentification
- `POST /api/auth/login/` - Connexion (obtenir token JWT)
- `POST /api/auth/refresh/` - Rafraîchir le token

### Zones Géographiques
- `GET /api/zones/` - Liste des zones (GeoJSON)
- `POST /api/zones/` - Créer une zone
- `GET /api/zones/{id}/` - Détails d'une zone
- `PUT /api/zones/{id}/` - Modifier une zone
- `DELETE /api/zones/{id}/` - Supprimer une zone
- `GET /api/zones/{id}/statistiques/` - Statistiques d'une zone

### Capteurs
- `GET /api/capteurs/` - Liste des capteurs (GeoJSON)
- `POST /api/capteurs/` - Créer un capteur
- `GET /api/capteurs/{id}/` - Détails d'un capteur
- `GET /api/capteurs/{id}/statistiques-mesures/` - Statistiques des mesures

### Mesures
- `GET /api/mesures/` - Liste des mesures
- `POST /api/mesures/` - Créer une mesure
- `GET /api/mesures/{id}/` - Détails d'une mesure

### Prédictions
- `GET /api/predictions/` - Liste des prédictions
- `POST /api/predictions/` - Créer une prédiction

### Alertes
- `GET /api/alertes/` - Liste des alertes
- `POST /api/alertes/` - Créer une alerte
- `PUT /api/alertes/{id}/resoudre/` - Marquer comme résolue

### Documentation API
- `GET /api/docs/` - Interface Swagger UI
- `GET /api/redoc/` - Documentation ReDoc
- `GET /api/schema/` - Schéma OpenAPI JSON

## 🔐 Authentification

L'API utilise l'authentification JWT. Pour accéder aux endpoints protégés :

1. **Obtenir un token** :
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

2. **Utiliser le token** :
```bash
curl -H "Authorization: Bearer <votre_token>" \
  http://localhost:8000/api/zones/
```

## 📊 Modèles de Données

### Utilisateur
- Rôles : admin, scientifique, technicien, observateur
- Informations personnelles et organisationnelles

### Zone
- Géométrie polygonale PostGIS (SRID 4326)
- Niveau de risque : faible, modéré, élevé, critique
- Superficie et description

### Capteur
- Position géographique PostGIS (SRID 4326)
- Types : température, salinité, vent, houle, niveau_mer, pluviométrie
- État : actif, maintenance, défaillant
- Fréquence de mesure et précision

### Mesure
- Valeur numérique avec unité
- Timestamp et qualité des données
- Commentaires optionnels

### Prédiction
- Taux d'érosion prédit (m/an)
- Horizon de prédiction (jours)
- Niveau de confiance (%)
- Modèle utilisé et paramètres

### Alerte
- Niveaux : info, attention, critique, urgence
- Statut : active, résolue
- Zone et capteur concernés

## 🤖 Tâches Automatiques (Celery)

### Génération de Mesures
- Exécutée toutes les X minutes selon la fréquence des capteurs
- Génère des valeurs réalistes selon le type de capteur

### Nettoyage des Données
- Supprime les mesures de plus d'un an
- Optimise les performances de la base de données

### Surveillance des Capteurs
- Détecte les capteurs défaillants
- Génère des alertes automatiques

## 🗺️ Données Géospatiales

### Format GeoJSON
L'API retourne les données géospatiales au format GeoJSON standard :

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-1.2, 44.6], [-1.0, 44.6], [-1.0, 44.8], [-1.2, 44.8], [-1.2, 44.6]]]
      },
      "properties": {
        "nom": "Côte Atlantique - Arcachon",
        "niveau_risque": "modere",
        "superficie_km2": 150.5
      }
    }
  ]
}
```

### Requêtes Spatiales
PostGIS permet des requêtes spatiales avancées :
- Intersection de géométries
- Calcul de distances
- Analyse de proximité
- Requêtes temporelles-spatiales

## 🔧 Configuration Avancée

### Variables d'Environnement
```env
# Base de données
DATABASE_NAME=erosion_db
DATABASE_USER=postgres
DATABASE_PASSWORD=password
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# JWT
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# GDAL (Windows avec conda)
GDAL_DATA=C:\Users\user\miniconda3\Library\share\gdal
PROJ_LIB=C:\Users\user\miniconda3\Library\share\proj
GDAL_LIBRARY_PATH=C:\Users\user\miniconda3\Library\bin\gdal.dll
```

### Permissions
- **Admin** : Accès complet à tous les endpoints
- **Scientifique** : Lecture/écriture des données et prédictions
- **Technicien** : Gestion des capteurs et mesures
- **Observateur** : Lecture seule des données publiques

## 🐳 Déploiement

### Installation Locale (Recommandé)
Ce projet est conçu pour fonctionner avec PostgreSQL installé localement sur votre machine.

### Hébergement Cloud
Pour déployer sur un serveur cloud :
1. Installer PostgreSQL avec PostGIS sur le serveur
2. Configurer les variables d'environnement
3. Utiliser un serveur WSGI comme Gunicorn
4. Configurer un reverse proxy (Nginx)

## 📈 Monitoring et Logs

### Logs Django
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
        },
    },
    'loggers': {
        'erosion': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Métriques
- Nombre de zones surveillées
- Nombre de capteurs actifs
- Volume de données collectées
- Temps de réponse API
- Erreurs et exceptions

## 🧪 Tests

### Tests Unitaires
```bash
# Exécuter tous les tests
python manage.py test

# Tests spécifiques
python manage.py test erosion.tests.test_api
python manage.py test erosion.tests.test_models
```

### Tests d'Intégration
```bash
# Test de l'API complète
python manage.py test erosion.tests.test_integration
```

## 🔒 Sécurité

### Bonnes Pratiques
- Variables d'environnement pour les secrets
- Authentification JWT avec expiration
- Permissions granulaires par rôle
- Validation des données d'entrée
- Protection CORS configurée

### Production
- HTTPS obligatoire
- Rate limiting
- Logs de sécurité
- Sauvegarde régulière des données

## 📞 Support et Contribution

### Documentation API
- Swagger UI : `http://localhost:8000/api/docs/`
- ReDoc : `http://localhost:8000/api/redoc/`

### Commandes Utiles
```bash
# Générer des données de test
python manage.py simulate_data

# Créer des migrations
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Collecter les fichiers statiques
python manage.py collectstatic

# Shell Django
python manage.py shell
```

### Développement
1. Fork le projet
2. Créer une branche feature
3. Commiter les changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 👥 Équipe

- **Développeur Principal** : [Votre nom]
- **Architecture** : Django REST Framework + PostGIS
- **Version** : 1.0.0

---

**🌊 Surveillance Érosion Côtière - API Professionnelle pour la Protection des Littoraux**