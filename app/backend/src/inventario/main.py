from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Inventário")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    from .api.produtos import router as produtos_router
    from .api.movimentacoes import router as movimentacoes_router
    from .api.operacao import router as operacao_router
    from .api.vendas import router as vendas_router
    from .api.realtime import (
        router as realtime_router,
        iniciar_leitor_serial,
        parar_leitor_serial,
    )

    app.include_router(produtos_router)
    app.include_router(movimentacoes_router)
    app.include_router(operacao_router)
    app.include_router(vendas_router)
    app.include_router(realtime_router)

    @app.on_event("startup")
    def _startup() -> None:
        iniciar_leitor_serial()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        parar_leitor_serial()

    return app


app = create_app()
