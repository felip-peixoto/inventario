#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN  21   // SDA
#define RST_PIN 22  // RST

MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  SPI.begin();           // Inicia SPI nos pinos padrão (SCK=18, MISO=19, MOSI=23)
  rfid.PCD_Init();       // Inicia o leitor RC522
  delay(100);
  
  Serial.println("Aproxime um cartão ou tag RFID do leitor...");
  rfid.PCD_DumpVersionToSerial();  // Mostra a versão do firmware (teste de comunicação)
}

void loop() {
  // Verifica se há um cartão presente
  if (!rfid.PICC_IsNewCardPresent()) return;
  
  // Tenta ler o UID
  if (!rfid.PICC_ReadCardSerial()) return;
  
  Serial.print("UID da tag: ");
  for (byte i = 0; i < rfid.uid.size; i++) {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println();
  
  // Mostra o tipo da tag
  MFRC522::PICC_Type tipo = rfid.PICC_GetType(rfid.uid.sak);
  Serial.print("Tipo: ");
  Serial.println(rfid.PICC_GetTypeName(tipo));
  Serial.println();
  
  rfid.PICC_HaltA();      // Para a comunicação com o cartão
  rfid.PCD_StopCrypto1(); // Para a criptografia
}

