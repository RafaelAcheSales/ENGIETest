from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class PowerPlantType(str, Enum):
    GAS_FIRED = "gasfired"
    TURBOJET = "turbojet"
    WIND_TURBINE = "windturbine"

class Fuels(BaseModel):
    gas: float = Field(alias="gas(euro/MWh)")
    kerosine: float = Field(alias="kerosine(euro/MWh)")
    co2: Optional[float] = Field(default=0.0, alias="co2(euro/ton)")
    wind: float = Field(alias="wind(%)")

    class Config:
        validate_by_name = True


class PowerPlant(BaseModel):
    name: str
    type: PowerPlantType
    efficiency: float
    pmin: float
    pmax: float


class ProductionPlanRequest(BaseModel):
    load: float
    fuels: Fuels
    powerplants: List[PowerPlant]


class ProductionPlanItem(BaseModel):
    name: str
    p: float

def round_to_tenth(x: float) -> float:
    """Round a float to one decimal place."""
    return round(x * 10) / 10.0