from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from src.core.database import get_db
from src.core.models import User, Vehicle, Load
from src.core.schemas import VehicleCreate, VehicleOut, LoadCreate, LoadOut
from src.api.auth import get_current_user
from src.core.services import ground_vehicle, unground_vehicle, UNGROUND_AUTHORIZED_ROLES

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


@router.post("/vehicles/{vehicle_id}/ground", response_model=VehicleOut)
async def ground_vehicle_endpoint(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flags a truck as Grounded (Driver-reported issue, HD-5.3 lifecycle)."""
    try:
        return await ground_vehicle(db, vehicle_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/vehicles/{vehicle_id}/unground", response_model=VehicleOut)
async def unground_vehicle_endpoint(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Releases a grounded asset after repairs (Mechanic/Owner only)."""
    if current_user.role not in UNGROUND_AUTHORIZED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{current_user.role}' is not authorized to un-ground "
                f"vehicles. Only {', '.join(UNGROUND_AUTHORIZED_ROLES)} may "
                f"release an asset."
            ),
        )
    try:
        return await unground_vehicle(db, vehicle_id, actor_role=current_user.role)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))