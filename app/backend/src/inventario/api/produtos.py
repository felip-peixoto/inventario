from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..models import Produto
from ..schemas import ProdutoCreate, ProdutoRead, ProdutoUpdate

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
