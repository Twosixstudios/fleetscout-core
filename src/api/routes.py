from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from src.core.database import get_db
from src.core.models import User, Vehicle, Load
from src.core.schemas import VehicleCreate, VehicleOut, LoadCreate, LoadOut
from src.api.auth import get_current_user

router = APIRouter()

@router.post("/vehicles", response_model=VehicleOut)
async def create_vehicle(vehicle: VehicleCreate, db: AsyncSession = Depends(get_db)):
    db_vehicle = Vehicle(**vehicle.model_dump())
    db.add(db_vehicle)
    await db.commit()
    await db.refresh(db_vehicle)
    return db_vehicle

@router.get("/vehicles", response_model=List[VehicleOut])
async def get_vehicles(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Vehicle))
    return result.scalars().all()

@router.post("/loads", response_model=LoadOut)
async def create_load(load: LoadCreate, db: AsyncSession = Depends(get_db)):
    db_load = Load(**load.model_dump())
    db.add(db_load)
    await db.commit()
    await db.refresh(db_load)
    return db_load

@router.get("/loads", response_model=List[LoadOut])
async def get_loads(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Load))
    return result.scalars().all()