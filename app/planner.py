from .models import ProductionPlanRequest, ProductionPlanItem, PowerPlant, Fuels, round_to_tenth, PowerPlantType
import logging
from typing import List
from fastapi import HTTPException
logger = logging.getLogger("production-plan")

class RuntimePowerPlant:
	def __init__(self, fuels: Fuels, plant: PowerPlant) -> None:
		self.name = plant.name
		self.type = plant.type
		self.efficiency = plant.efficiency

		self.pmin, self.pmax = self._compute_effective_pmin_pmax(fuels, plant)

		self.generation_cost = self._compute_generation_cost(fuels, plant)
		self.p: float = 0.0 # Total power allocated to this plant


	def _compute_effective_pmin_pmax(self, fuels: Fuels, plant: PowerPlant) -> tuple[float, float]:
		"""Compute effective pmin and pmax considering wind percentage for wind turbines."""
		if self.type == PowerPlantType.WIND_TURBINE:
			effective_pmax = round_to_tenth(plant.pmax * fuels.wind / 100.0)
			return 0.0, effective_pmax
		return plant.pmin, plant.pmax
	
	def _compute_generation_cost(self, fuels: Fuels, plant: PowerPlant) -> float:
		"""Compute the generation cost per MWh for this plant."""
		match self.type:
			case PowerPlantType.WIND_TURBINE:
				base_cost = 0.0
			case PowerPlantType.GAS_FIRED:
				base_cost = fuels.gas / self.efficiency
			case PowerPlantType.TURBOJET:
				base_cost = fuels.kerosine / self.efficiency
			case _:
				raise ValueError(f"Unknown powerplant type: {self.type}")

		co2_cost = 0.0
		if fuels.co2 and self.type in (PowerPlantType.GAS_FIRED, PowerPlantType.TURBOJET):
			co2_cost = 0.3 * fuels.co2
		return base_cost + co2_cost

class PlanAllocator:
	def __init__(self, runtime_plants: List[RuntimePowerPlant], total_load: float) -> None:
		self.runtime_plants = runtime_plants
		self.total_load = total_load

	def _format_plan_response(self, plants: List[RuntimePowerPlant]) -> List[ProductionPlanItem]:
		response = []
		for plant in plants:
			response.append(ProductionPlanItem(name=plant.name, p=round_to_tenth(plant.p)))
		return response

	def calculate_plan(self) -> List[ProductionPlanItem]:
		# Test if we can cover the load
		if not self._can_cover_load():
			logger.error("Cannot cover the total load with available power plants.")
			raise HTTPException(status_code=400, detail="Insufficient power capacity to cover the total load.")
		

		# Calculate Merit Order
		self.runtime_plants.sort(key=lambda plant: plant.generation_cost)

		allocated_load = 0.0
		for plant in self.runtime_plants:
			remaining_load = self.total_load - allocated_load
			if remaining_load <= 0:
				break

			# Determine how much this plant can contribute
			possible_production = min(plant.pmax, remaining_load)
			if possible_production >= plant.pmin:
				plant.p = possible_production
				allocated_load += plant.p
			else:
				plant.p = 0.0  # Cannot operate below pmin
		if abs(allocated_load - self.total_load) > 0.1:
			logger.error("Could not exactly match the total load after allocation.")
			raise HTTPException(status_code=400, detail="Could not exactly match the total load with given power plants.")
		
		return self._format_plan_response(self.runtime_plants)

	def _can_cover_load(self) -> bool:
		# Sum up all pmax values
		total_pmax = sum(plant.pmax for plant in self.runtime_plants)
		return total_pmax >= self.total_load

def build_production_plan(input_data: ProductionPlanRequest) -> List[ProductionPlanItem]:
	total_load = input_data.load
	fuels = input_data.fuels
	powerplants = input_data.powerplants
	runtime_powerplants = _create_runtime_powerplants(fuels, powerplants)
	allocator = PlanAllocator(runtime_powerplants, total_load)
	return allocator.calculate_plan()

def _create_runtime_powerplants(fuels: Fuels, plants: List[PowerPlant]) -> List[RuntimePowerPlant]:
	runtime_plants = []
	for plant in plants:
		runtime_plant = RuntimePowerPlant(fuels, plant)
		logger.info(f"Created runtime plant: {runtime_plant.name}")
		runtime_plants.append(runtime_plant)
	return runtime_plants