# 📡 Configuration Arduino ESP32 → Backend Django

## ✅ Configuration actuelle

### 🌐 Backend Django
- **Adresse** : `http://172.20.10.3:8000`
- **Status** : ✅ Actif et en écoute sur le réseau local

### 🔌 Endpoints API

#### 1. Enregistrement du capteur
```
POST http://172.20.10.3:8000/api/sensors/info/
Content-Type: application/json
```

**Données envoyées par Arduino :**
```json
{
  "sensor_id": "DHT11_001",
  "sensor_type": "dht11",
  "mac_address": "XX:XX:XX:XX:XX:XX",
  "ip_address": "172.20.10.X",
  "ssid_wifi": "X",
  "frequence_mesure_secondes": 120,
  "precision": 0.1,
  "unite_mesure": "°C/%",
  "battery_voltage": 3.3,
  "wifi_signal": -50
}
```

**Mapping des types de capteurs :**
- `dht11` → `temperature`
- `dht22` → `temperature`
- `rain` → `pluviometrie`
- `water` → `niveau_mer`
- `temperature` → `temperature`
- `humidity` → `humidite`
- `pressure` → `pression`

#### 2. Envoi des mesures
```
POST http://172.20.10.3:8000/api/sensors/measurements/
Content-Type: application/json
```

**Données envoyées par Arduino :**
```json
{
  "mac_address": "XX:XX:XX:XX:XX:XX",
  "temperature": 29.2,
  "humidity": 57.0,
  "rain_percent": 100.0,
  "water_percent": 93.0,
  "timestamp": "2025-10-13T16:00:00Z",
  "battery_voltage": 3.3,
  "wifi_signal": -50,
  "cpu_temperature": 45.0,
  "uptime_seconds": 3600
}
```

## 📊 Données enregistrées

Le backend crée automatiquement :
1. **CapteurArduino** : Enregistrement du capteur avec ses caractéristiques
2. **MesureArduino** : Stockage de chaque mesure avec horodatage
3. **Assignation automatique** à une zone par défaut

## 🔄 Fréquence d'envoi (dans votre code Arduino)

- **Lecture capteurs** : Toutes les 5 secondes (local)
- **Envoi mesures** : Toutes les 2 minutes
- **Envoi info capteur** : Toutes les 1 heure

## 🌐 Serveur Web Local Arduino

Votre ESP32 héberge également une page web accessible à :
```
http://[IP_ESP32]
```
Affiche en temps réel :
- 🌡️ Température
- 💧 Humidité  
- 💦 Quantité d'eau
- ☔ Pluie

## 🔧 Configuration réseau actuelle

```arduino
const char* ssid = "X";
const char* password = "12345678";
const char* backendInfoURL = "http://172.20.10.3:8000/api/sensors/info/";
const char* backendMeasureURL = "http://172.20.10.3:8000/api/sensors/measurements/";
```

## ✅ Tout est opérationnel !

Votre Arduino ESP32 est maintenant connecté au backend Django et envoie automatiquement :
- ✅ Les informations du capteur (1x/heure)
- ✅ Les mesures de température, humidité, pluie et eau (1x/2min)
- ✅ Les métadonnées (batterie, WiFi, CPU, uptime)

Les données sont stockées dans PostgreSQL avec PostGIS pour l'analyse d'érosion côtière ! 🌊

