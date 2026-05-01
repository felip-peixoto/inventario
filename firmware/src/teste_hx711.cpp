#include "HX711.h"

// Pinos que ligamos no ESP32
const int LOADCELL_DOUT_PIN = 4;
const int LOADCELL_SCK_PIN = 5;

HX711 scale;

void setup() {
  Serial.begin(115200);
  Serial.println("Iniciando o teste do HX711...");

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
}

void loop() {
  if (scale.is_ready()) {
    // Lê o valor bruto (sem calibração de tara ou peso)
    long valor_bruto = scale.read(); 
    Serial.print("Valor Bruto da Célula: ");
    Serial.println(valor_bruto);
  } else {
    Serial.println("HX711 não encontrado. Verifique as ligações!");
  }
  delay(500); // Atualiza a cada meio segundo
}
