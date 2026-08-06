from types import SimpleNamespace
from unittest import TestCase

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan import (
	SeasonProductionPlan,
)


class TestSeasonProductionPlan(TestCase):
	def test_baseline_aggregates_targets_inputs_and_resources(self):
		plan = SimpleNamespace(
			production_targets=[
				SimpleNamespace(
					target_outgrowers=10,
					target_plots=9,
					target_hectares=50,
					planned_yield_kg_per_hectare=1000,
					planning_rate=1800,
					parent_seed_rate_per_hectare=20,
					planned_production_qty=0,
					planned_procurement_value=0,
					parent_seed_required_qty=0,
				)
			],
			input_requirements=[SimpleNamespace(estimated_cost=2500000)],
			resource_allocations=[
				SimpleNamespace(
					active=1,
					resource_role="Outgrower Supervisor",
					user="supervisor@example.com",
				),
				SimpleNamespace(
					active=1,
					resource_role="Quality Inspector",
					user="inspector@example.com",
				),
			],
		)

		SeasonProductionPlan.calculate_baseline(plan)

		self.assertEqual(plan.target_hectares, 50)
		self.assertEqual(plan.planned_production_qty, 50000)
		self.assertEqual(plan.planned_procurement_value, 90000000)
		self.assertEqual(plan.parent_seed_required_qty, 1000)
		self.assertEqual(plan.planned_input_cost, 2500000)
		self.assertEqual(plan.planned_supervisors, 1)
		self.assertEqual(plan.planned_inspectors, 1)

	def test_readiness_requires_every_mandatory_control(self):
		plan = SimpleNamespace(
			readiness_items=[
				SimpleNamespace(status="Ready", mandatory=1),
				SimpleNamespace(status="Not Applicable", mandatory=1),
				SimpleNamespace(status="In Progress", mandatory=0),
			]
		)

		SeasonProductionPlan.calculate_readiness(plan)

		self.assertEqual(plan.readiness_score, 50)
		self.assertEqual(plan.mandatory_readiness_complete, 1)
