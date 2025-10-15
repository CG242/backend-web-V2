#include <WiFi.h>
#include <HTTPClient.h>
#include "DHT.h"
#include <esp_system.h> // Pour l'uptime et temp CPU

// --- CONFIG WIFI ---
const char* ssid = "JBixx";
const char* password = "Jean1234";

// --- CONFIG CAPTEURS ---
#define DHTPIN 26
#define DHTTYPE DHT11
#define RAINPIN 33
#define WATERPIN 34

DHT dht(DHTPIN, DHTTYPE);

// --- BACKEND DJANGO (CORRIGÉ) ---
const char* backendMeasureURL = "http://192.168.137.191:8000/api/arduino/recevoir-donnees/";

// --- SERVEUR WEB LOCAL ---
WiFiServer server(80);

// --- VARIABLES TEMPS ---
unsigned long lastRead = 0;
unsigned long lastSendMeasure = 0;
const long readInterval = 5000;      // 5 sec
const long sendMeasureInterval = 120000; // 2 min

// --- BATTERY & WiFi ---
float batteryVoltage = 3.3;

// --- FONCTIONS UTILES ---
int getWifiRSSI() { return WiFi.RSSI(); }
float getCpuTemperature() { return 45.0 + (esp_random()%10)/10.0; } // Approximation
unsigned long getUptime() { return millis() / 1000; }

// --- FONCTION ENVOI JSON MESURES (CORRIGÉE) ---
void sendMeasurement(float temperature, float humidity) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ ESP32 non connecté au Wi-Fi. Mesures non envoyées.");
    return;
  }

  HTTPClient http;
  http.begin(backendMeasureURL);
  http.addHeader("Content-Type", "application/json");

  // Utiliser une MAC fixe qui existe dans Django
  String macAddr = "AA:BB:CC:DD:EE:01"; // MAC du capteur température Biarritz
  
  // Générer timestamp ISO
  String isoTime = "2025-10-13T16:00:00Z"; // Vous pouvez générer dynamiquement si besoin

  // Format JSON CORRECT pour Django
  String jsonTemp = "{";
  jsonTemp += "\"mac_address\":\"" + macAddr + "\",";
  jsonTemp += "\"sensor_type\":\"temperature\",";
  jsonTemp += "\"value\":" + String(temperature,1) + ",";
  jsonTemp += "\"unit\":\"°C\",";
  jsonTemp += "\"timestamp\":\"" + isoTime + "\",";
  jsonTemp += "\"battery_voltage\":" + String(batteryVoltage,1) + ",";
  jsonTemp += "\"wifi_signal\":" + String(getWifiRSSI()) + ",";
  jsonTemp += "\"cpu_temperature\":" + String(getCpuTemperature(),1) + ",";
  jsonTemp += "\"uptime_seconds\":" + String(getUptime());
  jsonTemp += "}";

  Serial.println("📤 Envoi mesures :");
  Serial.println(jsonTemp);

  int code = http.POST(jsonTemp);
  if(code > 0){
    Serial.print("✅ HTTP "); Serial.println(code);
    Serial.println(http.getString());
  } else {
    Serial.print("❌ Erreur HTTP : "); Serial.println(http.errorToString(code).c_str());
  }

  http.end();
}

// --- FONCTION ENVOI HUMIDITÉ ---
void sendHumidityMeasurement(float humidity) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ ESP32 non connecté au Wi-Fi. Mesures non envoyées.");
    return;
  }

  HTTPClient http;
  http.begin(backendMeasureURL);
  http.addHeader("Content-Type", "application/json");

  // Utiliser la MAC du capteur humidité
  String macAddr = "AA:BB:CC:DD:EE:02"; // MAC du capteur humidité Biarritz
  
  String isoTime = "2025-10-13T16:00:00Z";

  String jsonHumidity = "{";
  jsonHumidity += "\"mac_address\":\"" + macAddr + "\",";
  jsonHumidity += "\"sensor_type\":\"humidite\",";
  jsonHumidity += "\"value\":" + String(humidity,1) + ",";
  jsonHumidity += "\"unit\":\"%\",";
  jsonHumidity += "\"timestamp\":\"" + isoTime + "\",";
  jsonHumidity += "\"battery_voltage\":" + String(batteryVoltage,1) + ",";
  jsonHumidity += "\"wifi_signal\":" + String(getWifiRSSI()) + ",";
  jsonHumidity += "\"cpu_temperature\":" + String(getCpuTemperature(),1) + ",";
  jsonHumidity += "\"uptime_seconds\":" + String(getUptime());
  jsonHumidity += "}";

  Serial.println("📤 Envoi humidité :");
  Serial.println(jsonHumidity);

  int code = http.POST(jsonHumidity);
  if(code > 0){
    Serial.print("✅ HTTP "); Serial.println(code);
    Serial.println(http.getString());
  } else {
    Serial.print("❌ Erreur HTTP : "); Serial.println(http.errorToString(code).c_str());
  }

  http.end();
}

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
    Serial.println("🌐 Serveur Django : http://192.168.137.191:8000");
  } else {
    Serial.println("\n❌ Échec Wi-Fi !");
  }

  // Lancer serveur web
  server.begin();
  Serial.println("🌐 Serveur web local actif port 80");
}

void loop() {
  // --- Serveur web ---
  WiFiClient client = server.available();
  if(client){
    String request = client.readStringUntil('\r');
    client.flush();

    float temp = dht.readTemperature();
    float hum = dht.readHumidity();
    int rainValue = analogRead(RAINPIN);
    int waterValue = analogRead(WATERPIN);
    float rainPercent = map(rainValue, 4095, 0, 0, 100);
    float waterPercent = map(waterValue, 0, 4095, 0, 100);

    if(isnan(temp)) temp=0;
    if(isnan(hum)) hum=0;

    String html = "<!DOCTYPE html><html><head>";
    html += "<meta charset='UTF-8'><meta http-equiv='refresh' content='5'>";
    html += "<title>ESP32 Station</title>";
    html += "<style>body{font-family:Arial;text-align:center;background:#eef;padding-top:30px;}h1{color:#333;} .value{font-size:1.8em;}</style></head><body>";
    html += "<h1>🌦️ Station ESP32</h1>";
    html += "<p class='value'>🌡️ Température : " + String(temp,1) + " °C</p>";
    html += "<p class='value'>💧 Humidité : " + String(hum,1) + " %</p>";
    html += "<p class='value'>💦 Qte d'eau : " + String(waterPercent,1) + " %</p>";
    html += "<p class='value'>☔ Pluie : " + String(rainPercent,1) + " %</p>";
    html += "<p class='value'>📡 Wi-Fi : " + String(WiFi.RSSI()) + " dBm</p>";
    html += "<p class='value'>🔋 Batterie : " + String(batteryVoltage,1) + " V</p>";
    html += "</body></html>";

    client.println("HTTP/1.1 200 OK");
    client.println("Content-type:text/html");
    client.println();
    client.println(html);
    client.stop();
  }

  // --- Lecture capteurs ---
  if(millis() - lastRead >= readInterval){
    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();
    int rainValue = analogRead(RAINPIN);
    int waterValue = analogRead(WATERPIN);
    float rainPercent = map(rainValue, 4095, 0, 0, 100);
    float waterPercent = map(waterValue, 0, 4095, 0, 100);

    if(!isnan(temp) && !isnan(hum)){
      Serial.print("📊 Temp: "); Serial.print(temp);
      Serial.print(" °C | Hum: "); Serial.print(hum);
      Serial.print(" % | Qte eau: "); Serial.print(waterPercent);
      Serial.print(" % | Pluie: "); Serial.println(rainPercent);
    } else {
      Serial.println("⚠️ Erreur lecture DHT11 !");
    }

    lastRead = millis();
  }

  // --- Envoi mesures ---
  if(millis() - lastSendMeasure >= sendMeasureInterval){
    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();
    if(!isnan(temp) && !isnan(hum)){
      // Envoyer température
      sendMeasurement(temp, hum);
      delay(1000); // Pause entre les envois
      // Envoyer humidité
      sendHumidityMeasurement(hum);
    }
    lastSendMeasure = millis();
  }

  // --- Reconnexion Wi-Fi si perdu ---
  if(WiFi.status() != WL_CONNECTED){
    Serial.println("⚠️ Wi-Fi perdu. Tentative reconnexion...");
    WiFi.begin(ssid,password);
  }
}
