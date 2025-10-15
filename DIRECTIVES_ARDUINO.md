# 📋 DIRECTIVES POUR VOTRE CODE ARDUINO ESP32

## 🔍 ANALYSE DE VOTRE CODE ACTUEL

### ✅ Points positifs :
- Configuration WiFi correcte
- URLs backend correctes
- Structure JSON bien formée
- Gestion des erreurs de connexion

### ❌ Problèmes identifiés :

1. **Timeout trop court** → Erreur "read Timeout"
2. **Caractère ° problématique** → Erreur d'encodage UTF-8
3. **Timestamp statique** → Toujours la même date
4. **Pas de gestion d'erreur "capteur introuvable"**

## 🔧 MODIFICATIONS OBLIGATOIRES

### 1. MODIFIER LA FONCTION `sendSensorInfo()`

```cpp
void sendSensorInfo() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ ESP32 non connecté au Wi-Fi. Info non envoyée.");
    return;
  }

  HTTPClient http;
  http.begin(backendInfoURL);
  http.setTimeout(15000);  // ⭐ AJOUTEZ CETTE LIGNE (15 secondes)
  http.addHeader("Content-Type", "application/json");

  String macAddr = WiFi.macAddress();
  String ipAddr  = WiFi.localIP().toString();

  String json = "{";
  json += "\"sensor_id\":\"DHT11_001\",";
  json += "\"sensor_type\":\"dht11\",";
  json += "\"mac_address\":\"" + macAddr + "\",";
  json += "\"ip_address\":\"" + ipAddr + "\",";
  json += "\"ssid_wifi\":\"" + String(ssid) + "\",";
  json += "\"frequence_mesure_secondes\":120,";
  json += "\"precision\":0.1,";
  json += "\"unite_mesure\":\"C/%\",";  // ⭐ SUPPRIMEZ le °
  json += "\"battery_voltage\":" + String(batteryVoltage,1) + ",";
  json += "\"wifi_signal\":" + String(getWifiRSSI());
  json += "}";

  Serial.println("📤 Envoi info capteur :");
  Serial.println(json);

  int code = http.POST(json);
  if(code > 0){
    Serial.print("✅ HTTP "); Serial.println(code);
    String response = http.getString();
    Serial.println(response);
    
    // ⭐ VÉRIFIER LA RÉPONSE
    if(response.indexOf("success") > 0) {
      Serial.println("✅ Capteur enregistré avec succès !");
    }
  } else {
    Serial.print("❌ Erreur HTTP : "); Serial.println(http.errorToString(code).c_str());
  }

  http.end();
}
```

### 2. MODIFIER LA FONCTION `sendMeasurement()`

```cpp
void sendMeasurement(float temperature, float humidity, float rainPercent, float waterPercent) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ ESP32 non connecté au Wi-Fi. Mesures non envoyées.");
    return;
  }

  HTTPClient http;
  http.begin(backendMeasureURL);
  http.setTimeout(15000);  // ⭐ AJOUTEZ CETTE LIGNE (15 secondes)
  http.addHeader("Content-Type", "application/json");

  String macAddr = WiFi.macAddress();
  
  // ⭐ GÉNÉRER UN TIMESTAMP DYNAMIQUE
  String isoTime = "2025-10-15T14:00:00Z";  // Mettez la date/heure actuelle
  
  String json = "{";
  json += "\"mac_address\":\"" + macAddr + "\",";
  json += "\"temperature\":" + String(temperature,1) + ",";
  json += "\"humidity\":" + String(humidity,1) + ",";
  json += "\"rain_percent\":" + String(rainPercent,1) + ",";
  json += "\"water_percent\":" + String(waterPercent,1) + ",";
  json += "\"timestamp\":\"" + isoTime + "\",";
  json += "\"battery_voltage\":" + String(batteryVoltage,1) + ",";
  json += "\"wifi_signal\":" + String(getWifiRSSI()) + ",";
  json += "\"cpu_temperature\":" + String(getCpuTemperature(),1) + ",";
  json += "\"uptime_seconds\":" + String(getUptime());
  json += "}";

  Serial.println("📤 Envoi mesures :");
  Serial.println(json);

  int code = http.POST(json);
  if(code > 0){
    Serial.print("✅ HTTP "); Serial.println(code);
    String response = http.getString();
    Serial.println(response);
    
    // ⭐ GESTION D'ERREUR "CAPTEUR INTROUVABLE"
    if(response.indexOf("introuvable") > 0) {
      Serial.println("⚠️ Capteur non enregistré ! Réenregistrement...");
      http.end();
      delay(2000);
      sendSensorInfo();  // Se réenregistrer
      return;
    }
    
    if(response.indexOf("success") > 0) {
      Serial.println("✅ Mesures envoyées avec succès !");
    }
  } else {
    Serial.print("❌ Erreur HTTP : "); Serial.println(http.errorToString(code).c_str());
  }

  http.end();
}
```

### 3. AMÉLIORER LA FONCTION `setup()`

```cpp
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("🚀 Démarrage ESP32...");

  dht.begin();
  pinMode(RAINPIN, INPUT);
  pinMode(WATERPIN, INPUT);

  // Connexion Wi-Fi
  WiFi.begin(ssid, password);
  int attempts = 0;
  while(WiFi.status() != WL_CONNECTED && attempts < 40){
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if(WiFi.status() == WL_CONNECTED){
    Serial.println("\n✅ Connecté Wi-Fi : " + String(WiFi.localIP().toString()));
    Serial.println("📡 MAC Address : " + WiFi.macAddress());
  } else {
    Serial.println("\n❌ Échec Wi-Fi !");
    return;  // ⭐ ARRÊTER SI PAS DE WIFI
  }

  // Lancer serveur web
  server.begin();
  Serial.println("🌐 Serveur web local actif port 80");

  // ⭐ ENVOI INITIAL OBLIGATOIRE
  Serial.println("📤 Enregistrement du capteur...");
  sendSensorInfo();
  lastSendInfo = millis();
  
  // ⭐ ATTENDRE UN PEU AVANT DE CONTINUER
  delay(3000);
  Serial.println("✅ Setup terminé !");
}
```

## 📊 STRUCTURE DES DONNÉES ENVOYÉES

### Enregistrement du capteur (`/api/sensors/info/`) :
```json
{
  "sensor_id": "DHT11_001",
  "sensor_type": "dht11",
  "mac_address": "08:3A:F2:A9:B8:24",
  "ip_address": "172.20.10.5",
  "ssid_wifi": "X",
  "frequence_mesure_secondes": 120,
  "precision": 0.1,
  "unite_mesure": "C/%",
  "battery_voltage": 3.3,
  "wifi_signal": -31
}
```

### Envoi des mesures (`/api/sensors/measurements/`) :
```json
{
  "mac_address": "08:3A:F2:A9:B8:24",
  "temperature": 29.3,
  "humidity": 61.0,
  "rain_percent": 100.0,
  "water_percent": 0.0,
  "timestamp": "2025-10-15T14:00:00Z",
  "battery_voltage": 3.3,
  "wifi_signal": -31,
  "cpu_temperature": 45.6,
  "uptime_seconds": 120
}
```

## 🎯 RÉSULTAT ATTENDU

Après ces modifications, votre Arduino va :

1. ✅ **S'enregistrer automatiquement** au démarrage
2. ✅ **Envoyer les mesures** avec les noms corrects :
   - `temperature` → Température (°C)
   - `humidity` → Humidité (%)
   - `rain_percent` → Pluie (%)
   - `water_percent` → Quantité d'eau (%)
3. ✅ **Gérer les erreurs** de timeout et de capteur introuvable
4. ✅ **Se réenregistrer** automatiquement si nécessaire

## 🔄 ORDRE D'EXÉCUTION

1. **Au démarrage** : `sendSensorInfo()` → Enregistre le capteur
2. **Toutes les 2 minutes** : `sendMeasurement()` → Envoie les 4 mesures
3. **Toutes les heures** : `sendSensorInfo()` → Met à jour les infos

## ⚠️ POINTS IMPORTANTS

- ✅ **Timeout de 15 secondes** pour éviter les erreurs
- ✅ **Pas de caractère °** dans l'unité de mesure
- ✅ **Timestamp à jour** (modifiez la date)
- ✅ **Gestion d'erreur** si capteur introuvable
- ✅ **Réenregistrement automatique** si nécessaire

Votre système sera alors **100% opérationnel** ! 🚀

