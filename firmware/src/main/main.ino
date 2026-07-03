#include <SPI.h>
#include <MFRC522.h>
#include "HX711.h"
#include <Preferences.h>

// ============================================================
// Firmware unificado: leitor RFID (RC522) + balança (HX711)
// Envia leituras padronizadas em JSON pela Serial para o
// software de gestão no PC (protocolo definido no README abaixo).
// ============================================================

// ---------- Pinos (confirmados nos testes isolados) ----------
const int RFID_SS_PIN = 22;  // SDA
const int RFID_RST_PIN = 15; // RST
const int LOADCELL_DOUT_PIN = 25;
const int LOADCELL_SCK_PIN = 26;

// ---------- Objetos ----------
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
HX711 scale;
Preferences prefs;

// ---------- Configuração de amostragem / filtro ----------
const int JANELA_MEDIANA = 7;                  // nº de amostras usadas no filtro de mediana
const unsigned long INTERVALO_LEITURA_MS = 40; // taxa de amostragem bruta da balança (~25 Hz)
const unsigned long INTERVALO_ENVIO_MS = 200;  // taxa de envio do peso filtrado (~5 Hz)
const float ALPHA_EMA = 0.25f;                 // suavização exponencial aplicada após a mediana

float bufferPeso[JANELA_MEDIANA];
int idxBuffer = 0;
bool bufferCheio = false;
float pesoFiltrado = 0.0f;

unsigned long ultimaLeitura = 0;
unsigned long ultimoEnvio = 0;

float calibrationFactor = -218.8f; // ponto de partida (baseado no teste isolado); recalibrar com CAL:<fator>

// ---------- Filtro de mediana ----------
float medianaBuffer(float *buf, int n)
{
  float tmp[JANELA_MEDIANA];
  memcpy(tmp, buf, n * sizeof(float));
  for (int i = 1; i < n; i++)
  {
    float chave = tmp[i];
    int j = i - 1;
    while (j >= 0 && tmp[j] > chave)
    {
      tmp[j + 1] = tmp[j];
      j--;
    }
    tmp[j + 1] = chave;
  }
  return tmp[n / 2];
}

// ---------- Persistência de calibração (NVS) ----------
void carregarCalibracao()
{
  prefs.begin("balanca", true);
  calibrationFactor = prefs.getFloat("fator", calibrationFactor);
  long offset = prefs.getLong("offset", 0);
  prefs.end();
  scale.set_scale(calibrationFactor);
  scale.set_offset(offset);
}

void salvarCalibracao()
{
  prefs.begin("balanca", false);
  prefs.putFloat("fator", calibrationFactor);
  prefs.putLong("offset", scale.get_offset());
  prefs.end();
}

// ---------- Comandos recebidos do software (modo Administrador) ----------
// TARE        -> zera a tara com a balança vazia
// CAL:<fator> -> define o fator de escala (obtido durante calibração com peso conhecido)
void processarComandoSerial()
{
  if (!Serial.available())
    return;
  String linha = Serial.readStringUntil('\n');
  linha.trim();

  if (linha == "TARE")
  {
    scale.tare(15);
    salvarCalibracao();
    Serial.println("{\"type\":\"ack\",\"cmd\":\"TARE\"}");
  }
  else if (linha.startsWith("CAL:"))
  {
    float novoFator = linha.substring(4).toFloat();
    if (novoFator != 0)
    {
      calibrationFactor = novoFator;
      scale.set_scale(calibrationFactor);
      salvarCalibracao();
      Serial.println("{\"type\":\"ack\",\"cmd\":\"CAL\"}");
    }
  }
}

// ---------- Envio padronizado ----------
void enviarLeituraPeso(float pesoGramas)
{
  Serial.print("{\"type\":\"peso\",\"valor_g\":");
  Serial.print(pesoGramas, 2);
  Serial.print(",\"ts_ms\":");
  Serial.print(millis());
  Serial.println("}");
}

void enviarLeituraTag(const String &uidHex)
{
  Serial.print("{\"type\":\"tag\",\"uid\":\"");
  Serial.print(uidHex);
  Serial.print("\",\"ts_ms\":");
  Serial.print(millis());
  Serial.println("}");
}

String uidParaHex(const MFRC522::Uid &uid)
{
  String s;
  for (byte i = 0; i < uid.size; i++)
  {
    if (uid.uidByte[i] < 0x10)
      s += "0";
    s += String(uid.uidByte[i], HEX);
  }
  s.toUpperCase();
  return s;
}

void setup()
{
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  carregarCalibracao();

  for (int i = 0; i < JANELA_MEDIANA; i++)
    bufferPeso[i] = 0;

  Serial.println("{\"type\":\"status\",\"msg\":\"pronto\"}");
}

void loop()
{
  processarComandoSerial();

  unsigned long agora = millis();

  // --- Amostragem da balança ---
  if (agora - ultimaLeitura >= INTERVALO_LEITURA_MS && scale.is_ready())
  {
    ultimaLeitura = agora;
    float leituraBruta = scale.get_units(1);

    bufferPeso[idxBuffer] = leituraBruta;
    idxBuffer = (idxBuffer + 1) % JANELA_MEDIANA;
    if (idxBuffer == 0)
      bufferCheio = true;

    int n = bufferCheio ? JANELA_MEDIANA : idxBuffer;
    if (n >= 3)
    {
      float med = medianaBuffer(bufferPeso, n);
      pesoFiltrado = ALPHA_EMA * med + (1 - ALPHA_EMA) * pesoFiltrado;
    }
  }

  // --- Envio periódico do peso já filtrado ---
  if (agora - ultimoEnvio >= INTERVALO_ENVIO_MS)
  {
    ultimoEnvio = agora;
    enviarLeituraPeso(pesoFiltrado);
  }

  // --- Leitura de tag RFID (evento, não periódico) ---
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
  {
    String uidHex = uidParaHex(rfid.uid);
    enviarLeituraTag(uidHex);
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
}