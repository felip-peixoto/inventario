from __future__ import annotations

import asyncio
import json
import threading
from typing import Callable, Optional

import serial


class SerialReader:
    """Lê a porta serial do ESP32 em uma thread dedicada (pyserial é bloqueante)
    e publica cada evento já parseado (peso/tag/ack/status) de volta no loop
    assíncrono do FastAPI via `call_soon_threadsafe`.

    Protocolo esperado (uma linha JSON por evento), definido no firmware:
      {"type":"peso","valor_g":123.45,"ts_ms":...}
      {"type":"tag","uid":"04A1B2C3","ts_ms":...}
      {"type":"ack","cmd":"TARE"|"CAL"}
      {"type":"status","msg":"pronto"}
    """

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.connection: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._parar = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_evento: Optional[Callable[[dict], None]] = None

    def iniciar(self, loop: asyncio.AbstractEventLoop, on_evento: Callable[[dict], None]) -> None:
        """Chamado no startup do FastAPI. `on_evento(dict)` roda dentro do loop assíncrono."""
        self._loop = loop
        self._on_evento = on_evento
        self.connection = serial.Serial(self.port, self.baudrate, timeout=1)
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop_leitura, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self.connection:
            self.connection.close()

    def enviar_comando(self, comando: str) -> None:
        """Envia comandos de calibração (TARE / CAL:<fator>) pro ESP32 (modo Administrador)."""
        if self.connection and self.connection.is_open:
            self.connection.write((comando + "\n").encode("utf-8"))

    def _loop_leitura(self) -> None:
        while not self._parar.is_set():
            try:
                bruto = self.connection.readline()
            except serial.SerialException:
                break
            if not bruto:
                continue
            linha = bruto.decode("utf-8", errors="ignore").strip()
            if not linha:
                continue
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                # linha de boot do ESP32, lixo de baudrate, etc — ignora
                continue
            if self._loop is not None and self._on_evento is not None:
                self._loop.call_soon_threadsafe(self._on_evento, evento)
