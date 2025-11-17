import logging

from fastapi import FastAPI, HTTPException

from .models import ProductionPlanRequest, ProductionPlanItem
from .planner import build_production_plan

logging.basicConfig(
    level=logging.INFO
)
logger = logging.getLogger("production-plan")

app = FastAPI(
    title="Production Plan API",
    version="1.0.0",
    description="Compute an optimal production plan for powerplants for ENGIE test.",
)


@app.post("/productionplan", response_model=list[ProductionPlanItem])
async def production_plan(payload: ProductionPlanRequest) -> list[ProductionPlanItem]:
    """
    Calculate the optimal production plan given load, fuels and powerplants.
    """
    try:
        return build_production_plan(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while calculating plan")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
