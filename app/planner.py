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



# Example input load:
# {
#   "load": 910,
#   "fuels":
#   {
#     "gas(euro/MWh)": 13.4,
#     "kerosine(euro/MWh)": 50.8,
#     "co2(euro/ton)": 20,
#     "wind(%)": 60
#   },
#   "powerplants": [
#     {
#       "name": "gasfiredbig1",
#       "type": "gasfired",
#       "efficiency": 0.53,
#       "pmin": 100,
#       "pmax": 460
#     },
#     {
#       "name": "gasfiredbig2",
#       "type": "gasfired",
#       "efficiency": 0.53,
#       "pmin": 100,
#       "pmax": 460
#     },
#     {
#       "name": "gasfiredsomewhatsmaller",
#       "type": "gasfired",
#       "efficiency": 0.37,
#       "pmin": 40,
#       "pmax": 210
#     },
#     {
#       "name": "tj1",
#       "type": "turbojet",
#       "efficiency": 0.3,
#       "pmin": 0,
#       "pmax": 16
#     },
#     {
#       "name": "windpark1",
#       "type": "windturbine",
#       "efficiency": 1,
#       "pmin": 0,
#       "pmax": 150
#     },
#     {
#       "name": "windpark2",
#       "type": "windturbine",
#       "efficiency": 1,
#       "pmin": 0,
#       "pmax": 36
#     }
#   ]
# }

#Test
# Calculate how much power each of a multitude of different powerplants need to produce (a.k.a. the production-plan) when the load is given and taking into account the cost of the underlying energy sources (gas, kerosine) and the Pmin and Pmax of each powerplant.

# More in detail
# The load is the continuous demand of power. The total load at each moment in time is forecasted. For instance for Belgium you can see the load forecasted by the grid operator here.

# At any moment in time, all available powerplants need to generate the power to exactly match the load. The cost of generating power can be different for every powerplant and is dependent on external factors: The cost of producing power using a turbojet, that runs on kerosine, is higher compared to the cost of generating power using a gas-fired powerplant because of gas being cheaper compared to kerosine and because of the thermal efficiency of a gas-fired powerplant being around 50% (2 units of gas will generate 1 unit of electricity) while that of a turbojet is only around 30%. The cost of generating power using windmills however is zero. Thus deciding which powerplants to activate is dependent on the merit-order.

# When deciding which powerplants in the merit-order to activate (a.k.a. unit-commitment problem) the maximum amount of power each powerplant can produce (Pmax) obviously needs to be taken into account. Additionally gas-fired powerplants generate a certain minimum amount of power when switched on, called the Pmin.

# Performing the challenge
# Build a REST API exposing an endpoint /productionplan that accepts a POST of which the body contains a payload as you can find in the example_payloads directory and that returns a json with the same structure as in example_response.json and that manages and logs run-time errors.

# For calculating the unit-commitment, we prefer you not to rely on an existing (linear-programming) solver but instead write an algorithm yourself.

# Implementations can be submitted in either C# (on .Net 5 or higher) or Python (3.8 or higher) as these are (currently) the main languages we use in SPaaS. Along with the implementation should be a README that describes how to compile (if applicable) and launch the application.

# C# implementations should contain a project file to compile the application.
# Python implementations should contain a requirements.txt or a pyproject.toml (for use with poetry) to install all needed dependencies.
# Payload
# The payload contains 3 types of data:

# load: The load is the amount of energy (MWh) that need to be generated during one hour.
# fuels: based on the cost of the fuels of each powerplant, the merit-order can be determined which is the starting point for deciding which powerplants should be switched on and how much power they will deliver. Wind-turbine are either switched-on, and in that case generate a certain amount of energy depending on the % of wind, or can be switched off.
# gas(euro/MWh): the price of gas per MWh. Thus if gas is at 6 euro/MWh and if the efficiency of the powerplant is 50% (i.e. 2 units of gas will generate one unit of electricity), the cost of generating 1 MWh is 12 euro.
# kerosine(euro/Mwh): the price of kerosine per MWh.
# co2(euro/ton): the price of emission allowances (optionally to be taken into account).
# wind(%): percentage of wind. Example: if there is on average 25% wind during an hour, a wind-turbine with a Pmax of 4 MW will generate 1MWh of energy.
# powerplants: describes the powerplants at disposal to generate the demanded load. For each powerplant is specified:
# name:
# type: gasfired, turbojet or windturbine.
# efficiency: the efficiency at which they convert a MWh of fuel into a MWh of electrical energy. Wind-turbines do not consume 'fuel' and thus are considered to generate power at zero price.
# pmax: the maximum amount of power the powerplant can generate.
# pmin: the minimum amount of power the powerplant generates when switched on.
# response
# The response should be a json as in example_payloads/response3.json, which is the expected answer for example_payloads/payload3.json, specifying for each powerplant how much power each powerplant should deliver. The power produced by each powerplant has to be a multiple of 0.1 Mw and the sum of the power produced by all the powerplants together should equal the load.

# Want more challenge?
# Having fun with this challenge and want to make it more realistic. Optionally, do one of the extra's below:

# Docker
# Provide a Dockerfile along with the implementation to allow deploying your solution quickly.

# CO2
# Taken into account that a gas-fired powerplant also emits CO2, the cost of running the powerplant should also take into account the cost of the emission allowances. For this challenge, you may take into account that each MWh generated creates 0.3 ton of CO2.