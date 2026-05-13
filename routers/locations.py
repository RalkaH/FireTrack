# routers/locations.py
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from models import Location
from schemas import LocationCreate, LocationRead

router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
)


@router.get("/", response_model=List[LocationRead])
def list_locations(db: Session = Depends(get_db)):
    return db.query(Location).all()


@router.post(
    "/",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(data: LocationCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(Location)
        .filter(Location.name == data.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Место с таким названием уже существует",
        )

    loc = Location(
        name=data.name,
        description=data.description,
        created_at=datetime.utcnow(),
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc
