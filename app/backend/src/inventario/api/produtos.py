from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..models import Produto
from ..schemas import AjusteEstoque, MovimentacaoRead, ProdutoCreate, ProdutoRead, ProdutoUpdate
from ..services import SemMudanca, aplicar_ajuste_estoque

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("", response_model=list[ProdutoRead])
def listar(session: Session = Depends(get_session)):
    return session.exec(select(Produto).order_by(Produto.nome)).all()


@router.post("", response_model=ProdutoRead, status_code=status.HTTP_201_CREATED)
def criar(dados: ProdutoCreate, session: Session = Depends(get_session)):
    produto = Produto(**dados.model_dump())
    session.add(produto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "rfid_tag_id já cadastrado")
    session.refresh(produto)
    return produto


@router.get("/{produto_id}", response_model=ProdutoRead)
def obter(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    return produto


@router.put("/{produto_id}", response_model=ProdutoRead)
def atualizar(produto_id: int, dados: ProdutoUpdate, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)
    session.add(produto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "rfid_tag_id já cadastrado")
    session.refresh(produto)
    return produto


@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    session.delete(produto)
    session.commit()


@router.post(
    "/{produto_id}/ajustar-estoque",
    response_model=MovimentacaoRead,
    status_code=status.HTTP_201_CREATED,
)
def ajustar_estoque(produto_id: int, dados: AjusteEstoque, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não encontrado")
    try:
        mov = aplicar_ajuste_estoque(session, produto, dados.nova_quantidade)
    except SemMudanca:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "estoque já está nesse valor")
    return MovimentacaoRead(
        id=mov.id,
        produto_id=mov.produto_id,
        produto_nome=produto.nome,
        tipo=mov.tipo,
        quantidade=mov.quantidade,
        peso_g=mov.peso_g,
        criado_em=mov.criado_em,
    )
