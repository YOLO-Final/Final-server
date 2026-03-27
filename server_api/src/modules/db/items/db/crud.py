from sqlalchemy.orm import Session

from src.modules.db.items.db.model import Item
from src.modules.db.items.db.schema import ItemCreate, ItemUpdate


def create_item(db: Session, item_in: ItemCreate) -> Item:
    item = Item(title=item_in.title, description=item_in.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int) -> Item | None:
    return db.query(Item).filter(Item.id == item_id).first()


def list_items(db: Session, skip: int = 0, limit: int = 100) -> list[Item]:
    return db.query(Item).offset(skip).limit(limit).all()


def update_item(db: Session, db_item: Item, item_in: ItemUpdate) -> Item:
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, db_item: Item) -> None:
    db.delete(db_item)
    db.commit()
