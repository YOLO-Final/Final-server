from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.lib.database import get_db
from src.modules.db.items.db import crud
from src.modules.db.items.db.schema import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item_endpoint(item_in: ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db=db, item_in=item_in)


@router.get("", response_model=list[ItemRead])
def list_items_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.list_items(db=db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=ItemRead)
def get_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db=db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=ItemRead)
def update_item_endpoint(item_id: int, item_in: ItemUpdate, db: Session = Depends(get_db)):
    item = crud.get_item(db=db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return crud.update_item(db=db, db_item=item, item_in=item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db=db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    crud.delete_item(db=db, db_item=item)
    return None
