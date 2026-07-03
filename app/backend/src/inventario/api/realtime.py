from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from ..db import engine, settings
from ..domain.inventory import reconcile
from ..domain.weight import WeightBuffer
from ..models import Produto
from ..serial_reader import SerialReader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

_clientes: set[WebSocket] = set()
_leitor = SerialReader(settings.serial_port, settings.serial_baud)

# só existe uma balança física ligada por vez, então o estado da "estação
# de pesagem" pode viver como estado de módulo mesmo
_produto_ativo_id: int | None = None
_buffer = WeightBuffer(settings.weight_stability_samples, settings.weight_stability_tolerance_g)
_ultimo_preview_enviado: tuple | None = None


async def _broadcast(evento: dict) -> None:
    msg = json.dumps(evento, default=str)
    mortos = []
    for ws in _clientes:
        try:
            await ws.send_text(msg)
        except Exception:
            mortos.append(ws)
    for ws in mortos:
        _clientes.discard(ws)


def _buscar_produto_por_tag(uid: str) -> Produto | None:
    with Session(engine) as session:
        return session.exec(select(Produto).where(Produto.rfid_tag_id == uid)).first()


def _montar_preview(produto: Produto, peso_g: Decimal) -> dict:
    r = reconcile(
        produto_id=produto.id,
        peso_g=peso_g,
        tara_g=produto.tara_caixa_g,
        peso_unitario_g=produto.peso_unitario_g,
        estoque_disponivel=produto.estoque_disponivel,
        rounding_tolerance_units=settings.rounding_tolerance_units,
        empty_scale_tolerance_g=settings.empty_scale_tolerance_g,
    )
    preview = {
        "type": "preview",
        "status": r.status.value,
        "produto_id": produto.id,
        "produto_nome": produto.nome,
        "estoque_atual": produto.estoque_disponivel,
        "peso_g": str(peso_g),
        "tipo": None,
        "quantidade": None,
        "qtd_fisica": None,
        "qtd_resultante": None,
    }
    if r.movement is not None:
        preview["tipo"] = r.movement.tipo
        preview["quantidade"] = r.movement.quantidade
        preview["qtd_fisica"] = r.movement.qtd_fisica
        preview["qtd_resultante"] = r.movement.qtd_resultante
    return preview


def _on_evento_serial(evento: dict) -> None:
    global _produto_ativo_id, _buffer, _ultimo_preview_enviado

    tipo_evento = evento.get("type")

    if tipo_evento == "tag":
        uid = str(evento.get("uid", "")).upper()
        produto = _buscar_produto_por_tag(uid)
        _buffer = WeightBuffer(settings.weight_stability_samples, settings.weight_stability_tolerance_g)
        _ultimo_preview_enviado = None

        if produto is None:
            _produto_ativo_id = None
            asyncio.create_task(_broadcast({"type": "produto_desconhecido", "uid": uid}))
        else:
            _produto_ativo_id = produto.id
            asyncio.create_task(_broadcast({
                "type": "tag",
                "uid": uid,
                "produto_id": produto.id,
                "produto_nome": produto.nome,
            }))
        return

    if tipo_evento == "peso":
        valor = Decimal(str(evento.get("valor_g", 0)))
        asyncio.create_task(_broadcast({"type": "peso", "valor_g": str(valor)}))

        if _produto_ativo_id is None:
            return

        _buffer.add(valor)
        estavel = _buffer.stable_value()
        if estavel is None:
            return

        with Session(engine) as session:
            produto = session.get(Produto, _produto_ativo_id)
        if produto is None:
            return

        preview = _montar_preview(produto, estavel)
        # evita reenviar o mesmo resultado a cada nova amostra estável
        chave = (preview["status"], preview["quantidade"])
        if chave != _ultimo_preview_enviado:
            _ultimo_preview_enviado = chave
            asyncio.create_task(_broadcast(preview))


def iniciar_leitor_serial() -> None:
    try:
        loop = asyncio.get_event_loop()
        _leitor.iniciar(loop, _on_evento_serial)
        logger.info("leitor serial conectado em %s", settings.serial_port)
    except Exception as e:
        # não derruba o backend se o ESP32 não estiver plugado durante o desenvolvimento
        logger.warning("não foi possível abrir a porta serial (%s): %s", settings.serial_port, e)


def parar_leitor_serial() -> None:
    _leitor.parar()


@router.websocket("/ws/pesagem")
async def ws_pesagem(websocket: WebSocket):
    await websocket.accept()
    _clientes.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantém viva; ignoramos msgs do cliente
    except WebSocketDisconnect:
        _clientes.discard(websocket)
