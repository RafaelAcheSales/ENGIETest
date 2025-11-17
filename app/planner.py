from .models import ProductionPlanRequest, ProductionPlanItem, PowerPlant, Fuels, round_to_tenth, PowerPlantType
import logging
from fastapi import HTTPException
logger = logging.getLogger("production-plan")

# Assuming an average CO2 emission per MWh for fossil fuel plants
CO2_EMISSION_PER_MWH = 0.3

class RuntimePowerPlant:
	""" Represents a power plant during runtime with computed attributes for planning."""
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
			co2_cost = CO2_EMISSION_PER_MWH * fuels.co2
		return base_cost + co2_cost

class PlanAllocator:
	""" Allocate power production to power plants based on merit order and load requirements."""
	def __init__(self, runtime_plants: list[RuntimePowerPlant], total_load: float) -> None:
		self.runtime_plants = runtime_plants
		self.total_load = total_load

	def _format_plan_response(self, plants: list[RuntimePowerPlant]) -> list[ProductionPlanItem]:
		"""Format the production plan API response."""
		response = []
		for plant in plants:
			response.append(ProductionPlanItem(name=plant.name, p=round_to_tenth(plant.p)))
		return response

	def calculate_plan(self) -> list[ProductionPlanItem]:
		""" Calculate the production plan to meet the total load."""
		if not self._can_cover_load():
			logger.error("Cannot cover the total load with available power plants.")
			raise HTTPException(status_code=400, detail="Insufficient power capacity to cover the total load.")
		
		logger.info("Sufficient capacity to cover the load. Proceeding with allocation.")
		# Calculate Merit Order
		self.runtime_plants.sort(key=lambda plant: plant.generation_cost)

		allocated_load = 0.0
		for plant in self.runtime_plants:
			remaining_load = self.total_load - allocated_load
			if remaining_load <= 0:
				break

			# Determine how much this plant can contribute
			possible_production = min(plant.pmax, remaining_load)
			# Use pmin if possible production is less than pmin
			# This could possibly be improved for more efficient allocation
			plant.p = possible_production if possible_production >= plant.pmin else plant.pmin

			allocated_load += plant.p
			logger.info(f"Allocated {plant.p} MW to plant {plant.name}")
		
		return self._format_plan_response(self.runtime_plants)

	def _can_cover_load(self) -> bool:
		""" Check if the total pmax of all plants can cover the required load."""
		total_pmax = sum(plant.pmax for plant in self.runtime_plants)
		return total_pmax >= self.total_load

def build_production_plan(input_data: ProductionPlanRequest) -> list[ProductionPlanItem]:
	""" Build the production plan based on input data."""
	total_load = input_data.load
	fuels = input_data.fuels
	powerplants = input_data.powerplants
	runtime_powerplants = _create_runtime_powerplants(fuels, powerplants)
	allocator = PlanAllocator(runtime_powerplants, total_load)
	return allocator.calculate_plan()

def _create_runtime_powerplants(fuels: Fuels, plants: list[PowerPlant]) -> list[RuntimePowerPlant]:
	"""" Create runtime power plant instances from input data."""
	runtime_plants = []
	for plant in plants:
		runtime_plant = RuntimePowerPlant(fuels, plant)
		logger.info(f"Created runtime plant: {runtime_plant.name}")
		runtime_plants.append(runtime_plant)
	return runtime_plants