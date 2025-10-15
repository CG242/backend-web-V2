# 🤖 Fonctionnalité Machine Learning - Prédiction d'Érosion

## 📋 Vue d'ensemble

Cette fonctionnalité ajoute des capacités de Machine Learning à votre backend d'érosion côtière, permettant de prédire automatiquement les taux d'érosion en utilisant des modèles entraînés sur vos données historiques.

## 🏗️ Architecture ML

### Modèles Django

#### `ModeleML`
- **Nom**: Nom du modèle (ex: "Random Forest Erosion")
- **Version**: Version du modèle (ex: "1.20241201")
- **Type**: Type d'algorithme (Random Forest, Régression Linéaire, etc.)
- **Statut**: Actif/Inactif/En entraînement/Erreur
- **Chemin fichier**: Chemin vers le fichier .joblib sauvegardé
- **Score de précision**: R² score du modèle
- **Features utilisées**: Liste des features utilisées pour l'entraînement

#### `Prediction` (nouveau modèle)
- **Zone**: Zone géographique concernée
- **Modèle ML**: Modèle utilisé pour la prédiction
- **Horizon**: Horizon de prédiction en jours
- **Taux prédit**: Taux d'érosion prédit (m/an)
- **Intervalle de confiance**: Min/Max avec largeur
- **Confiance**: Pourcentage de confiance
- **Features d'entrée**: Données utilisées pour la prédiction

### Services ML

#### `MLPredictionService`
- **`predire_erosion(zone_id, features, horizon_jours)`**: Fonction principale de prédiction
- Charge le modèle actif
- Prépare les features (capteurs, historique, environnementales)
- Calcule la prédiction avec intervalle de confiance
- Sauvegarde en base de données

#### `MLTrainingService`
- **`train_models()`**: Entraîne Random Forest et Régression Linéaire
- Prépare les données d'entraînement depuis l'historique d'érosion
- Divise en train/test (80/20)
- Évalue les performances (R², MSE)
- Sauvegarde les modèles et sélectionne le meilleur

## 🚀 Utilisation

### 1. Entraînement des Modèles

```bash
# Entraîner les modèles ML
python manage.py train_ml_models

# Avec options
python manage.py train_ml_models --force --verbose --models random_forest regression_lineaire
```

**Prérequis:**
- Minimum 10 mesures d'érosion historiques
- Au moins une zone configurée
- Données des capteurs Arduino (optionnel)

### 2. Prédiction via API

#### Endpoint principal
```bash
POST /api/predict/
```

**Exemple de requête:**
```json
{
    "zone_id": 1,
    "horizon_jours": 30,
    "features": {
        "temperature_supplementaire": 25.5,
        "vent_supplementaire": 15.2
    },
    "commentaires": "Prédiction pour analyse saisonnière"
}
```

**Réponse:**
```json
{
    "success": true,
    "message": "Prédiction générée avec succès pour la zone Côte Atlantique",
    "prediction": {
        "id": 123,
        "zone": 1,
        "zone_nom": "Côte Atlantique",
        "modele_ml": 5,
        "modele_nom": "Random Forest Erosion",
        "modele_version": "1.20241201",
        "modele_type": "random_forest",
        "date_prediction": "2024-12-01T10:30:00Z",
        "horizon_jours": 30,
        "taux_erosion_pred_m_an": 0.15,
        "taux_erosion_min_m_an": 0.12,
        "taux_erosion_max_m_an": 0.18,
        "intervalle_confiance": {
            "min": 0.12,
            "max": 0.18,
            "largeur": 0.06
        },
        "confiance_pourcentage": 85.5,
        "score_confiance": 0.855,
        "features_entree": {...},
        "commentaires": "Prédiction générée par Random Forest Erosion v1.20241201"
    }
}
```

#### Autres endpoints

```bash
# Récupérer le modèle actif
GET /api/models/active/

# Performances d'un modèle
GET /api/models/{model_id}/performance/

# Prédictions d'une zone
GET /api/zones/{zone_id}/predictions/?limit=10&horizon_jours=30
```

### 3. Tâches Celery Automatiques

#### Prédictions automatiques
```python
# Calculer les prédictions pour toutes les zones
from erosion.tasks import calculer_predictions_automatiques
calculer_predictions_automatiques.delay()
```

#### Entraînement automatique
```python
# Entraîner les modèles automatiquement
from erosion.tasks import entrainer_modeles_ml
entrainer_modeles_ml.delay()
```

#### Configuration Celery Beat
Ajoutez ces tâches à votre `celery_beat_schedule.py`:

```python
CELERY_BEAT_SCHEDULE = {
    # Prédictions automatiques quotidiennes
    'predictions-automatiques': {
        'task': 'erosion.tasks.calculer_predictions_automatiques',
        'schedule': crontab(hour=6, minute=0),  # Tous les jours à 6h
    },
    
    # Entraînement hebdomadaire
    'entrainement-modeles': {
        'task': 'erosion.tasks.entrainer_modeles_ml',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Lundi à 2h
    },
    
    # Évaluation des performances
    'evaluation-performance': {
        'task': 'erosion.tasks.evaluer_performance_modeles',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Lundi à 3h
    },
    
    # Nettoyage des anciennes données
    'nettoyage-predictions': {
        'task': 'erosion.tasks.nettoyer_anciennes_predictions_ml',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Lundi à 4h
    },
}
```

## 🔧 Configuration

### Variables d'environnement

```env
# Répertoire des modèles ML
ML_MODELS_DIR=ml_models/

# Paramètres d'entraînement
ML_MIN_TRAINING_SAMPLES=10
ML_TRAIN_TEST_SPLIT=0.2
ML_RANDOM_STATE=42
```

### Structure des fichiers

```
backend/
├── ml_models/                    # Modèles sauvegardés
│   ├── random_forest_20241201_103000.joblib
│   └── linear_regression_20241201_103000.joblib
├── reports/                      # Rapports de performance
│   └── ml_performance_20241201.json
└── exports/                     # Exports pour IA
    └── ia/donnees_entrainement_20241201.json
```

## 📊 Features Utilisées

### Features de base
- **Superficie de la zone** (km²)
- **Niveau de risque** (encodé numériquement)

### Features des capteurs Arduino
- **Température actuelle** et moyenne 7j
- **Humidité actuelle** et moyenne 7j
- **Pression atmosphérique**
- **pH de l'eau**
- **Salinité**

### Features historiques
- **Dernière mesure d'érosion**
- **Précision de la dernière mesure**
- **Moyenne/min/max sur 12 mois**
- **Nombre de mesures sur 12 mois**

### Features environnementales
- **Température moyenne** (données externes)
- **Vitesse du vent**
- **Précipitations totales**
- **Niveau de mer moyen**
- **Élévation moyenne**

### Features supplémentaires
- **Données météo** (via APIs externes)
- **Données satellites** (via NASA GIBS)
- **Données marines** (via Copernicus)

## 🎯 Algorithme de Prédiction

### 1. Préparation des données
- Récupération des features de la zone
- Normalisation des données (StandardScaler pour régression linéaire)
- Filtrage selon les features utilisées par le modèle

### 2. Calcul de la prédiction
- **Random Forest**: Utilise la variance des arbres pour l'intervalle de confiance
- **Régression Linéaire**: Estimation basique avec marge de 20%

### 3. Intervalle de confiance
- **Random Forest**: ±2σ basé sur la variance des prédictions des arbres
- **Régression Linéaire**: ±20% de la prédiction principale

### 4. Score de confiance
- **Random Forest**: 100 - (std_dev × 10)
- **Régression Linéaire**: 75% par défaut

## 🔒 Permissions

### Rôles utilisateur
- **Admin**: Accès complet à tous les endpoints
- **Scientifique**: Peut prédire sur toutes les zones
- **Technicien**: Peut prédire sur les zones de son organisation
- **Observateur**: Accès refusé aux prédictions

### Authentification
- **JWT obligatoire** pour tous les endpoints
- **Validation des permissions** par zone
- **Audit trail** complet des prédictions

## 📈 Monitoring et Performance

### Métriques importantes
- **Score R²** des modèles
- **Erreur quadratique moyenne (MSE)**
- **Nombre de prédictions** par modèle
- **Confiance moyenne** des prédictions
- **Temps de réponse** des prédictions

### Logs
- **Entraînement**: Logs détaillés des performances
- **Prédictions**: Logs des features utilisées
- **Erreurs**: Logs des échecs avec détails

### Rapports
- **Rapport quotidien ML**: Statistiques des prédictions
- **Rapport de performance**: Évaluation des modèles
- **Export IA**: Données formatées pour l'entraînement

## 🚨 Gestion d'erreurs

### Erreurs communes
- **Aucun modèle actif**: Vérifier qu'un modèle est entraîné
- **Pas assez de données**: Minimum 10 échantillons requis
- **Modèle non trouvé**: Vérifier le chemin du fichier
- **Features manquantes**: Vérifier les données des capteurs

### Fallback
- **Prédiction par défaut**: 0.1 m/an avec 50% de confiance
- **Modèle de secours**: Utiliser le dernier modèle entraîné
- **Logs d'erreur**: Enregistrement complet des échecs

## 🔄 Maintenance

### Tâches régulières
- **Entraînement hebdomadaire** des modèles
- **Nettoyage mensuel** des anciennes prédictions
- **Évaluation trimestrielle** des performances
- **Archivage annuel** des données d'entraînement

### Commandes utiles
```bash
# Entraîner les modèles
python manage.py train_ml_models --force --verbose

# Vérifier les modèles actifs
python manage.py shell
>>> from erosion.models import ModeleML
>>> ModeleML.objects.filter(statut='actif')

# Tester une prédiction
python manage.py shell
>>> from erosion.services import MLPredictionService
>>> service = MLPredictionService()
>>> prediction = service.predire_erosion(zone_id=1, horizon_jours=30)
```

## 📚 Documentation API

### Swagger UI
- **URL**: `http://localhost:8000/api/docs/`
- **Tags**: "Prédictions ML" et "Modèles ML"
- **Exemples**: Requêtes et réponses complètes
- **Schémas**: Validation automatique des données

### Endpoints documentés
- `POST /api/predict/` - Prédiction d'érosion
- `GET /api/models/active/` - Modèle actif
- `GET /api/models/{id}/performance/` - Performances
- `GET /api/zones/{id}/predictions/` - Prédictions d'une zone

## 🎉 Exemples d'utilisation

### Frontend JavaScript
```javascript
// Prédiction d'érosion
const response = await fetch('/api/predict/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        zone_id: 1,
        horizon_jours: 30,
        features: {
            temperature_supplementaire: 25.5
        }
    })
});

const result = await response.json();
console.log('Prédiction:', result.prediction);
```

### Python Client
```python
import requests

# Prédiction d'érosion
response = requests.post(
    'http://localhost:8000/api/predict/',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'zone_id': 1,
        'horizon_jours': 30,
        'features': {'temperature_supplementaire': 25.5}
    }
)

prediction = response.json()['prediction']
print(f"Taux d'érosion prédit: {prediction['taux_erosion_pred_m_an']} m/an")
print(f"Confiance: {prediction['confiance_pourcentage']}%")
```

---

**🤖 Cette fonctionnalité ML transforme votre backend en un système intelligent de prédiction d'érosion, capable d'apprendre de vos données et de fournir des prédictions précises avec intervalles de confiance !**
