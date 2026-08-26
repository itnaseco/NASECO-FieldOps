from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan import (
	SeasonProductionPlan,
	aggregate_input_requirements,
	aggregate_parent_seed_requirements,
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
					target_acres=0,
					planned_yield_kg_per_acre=0,
					planned_production_qty=0,
				)
			],
			parent_seed_requirements=[
				SimpleNamespace(parent_role="Female", required_stock_qty=800),
				SimpleNamespace(parent_role="Male", required_stock_qty=200),
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
		self.assertAlmostEqual(plan.target_acres, 123.5526907335)
		self.assertEqual(plan.planned_production_qty, 50000)
		self.assertEqual(plan.female_parent_seed_required_qty, 800)
		self.assertEqual(plan.male_parent_seed_required_qty, 200)
		self.assertEqual(plan.parent_seed_required_qty, 1000)
		self.assertAlmostEqual(plan.production_targets[0].planned_yield_kg_per_acre, 404.68564224)
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

	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.frappe.get_doc")
	def test_input_requirements_are_aggregated_from_target_recipes(self, get_doc):
		get_doc.return_value = SimpleNamespace(
			inputs=[
				SimpleNamespace(
					resource_type="Stock Item", item_code="FO-GLYPHOSATE",
					source_warehouse="Main Stores", recovery_policy="Fully Recoverable",
					recoverable_percent=100, stock_quantity_per_hectare=2,
					quantity_per_hectare=0, conversion_factor=1,
				)
			],
			stages=[],
		)
		targets = [
			SimpleNamespace(
				crop_recipe="Maize Recipe", target_hectares=hectares,
			)
			for hectares in (5, 7)
		]

		parent_seed_requirements = [SimpleNamespace(
			item_code="PARENT-SEED", source_warehouse="Seed Stores",
			recovery_policy="Fully Recoverable", recoverable_percent=100,
			required_stock_qty=120,
		)]
		rows = aggregate_input_requirements(targets, parent_seed_requirements)

		by_item = {row["item_code"]: row for row in rows}
		self.assertEqual(by_item["FO-GLYPHOSATE"]["required_qty"], 24)
		self.assertEqual(by_item["PARENT-SEED"]["required_qty"], 120)
		self.assertEqual(get_doc.call_count, 2)

	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.get_recipe_variety_yield")
	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.frappe.get_doc")
	def test_recipe_yield_is_snapshotted_when_recipe_changes(self, get_doc, get_recipe_yield):
		get_recipe_yield.return_value = 4200
		target = SimpleNamespace(
			crop_recipe="Bazooka Standard", yield_source_recipe=None,
			recipe_yield_kg_per_hectare=0, planned_yield_kg_per_hectare=0,
			yield_override_reason="Old override",
		)
		plan = SimpleNamespace(production_targets=[target])

		SeasonProductionPlan.sync_target_recipe_yields(plan)

		self.assertEqual(target.recipe_yield_kg_per_hectare, 4200)
		self.assertEqual(target.planned_yield_kg_per_hectare, 4200)
		self.assertEqual(target.yield_source_recipe, "Bazooka Standard")
		self.assertIsNone(target.yield_override_reason)

		target.planned_yield_kg_per_hectare = 3900
		target.yield_override_reason = "Regional forecast adjustment"
		SeasonProductionPlan.sync_target_recipe_yields(plan)

		self.assertEqual(target.recipe_yield_kg_per_hectare, 4200)
		self.assertEqual(target.planned_yield_kg_per_hectare, 3900)
		self.assertEqual(get_recipe_yield.call_count, 1)

	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.get_item_uom_conversion")
	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.frappe.get_doc")
	def test_parent_seed_requirements_include_all_recipe_roles(self, get_doc, get_conversion):
		get_doc.return_value = SimpleNamespace(parent_seed_items=[
			SimpleNamespace(
				ratio_group="Primary", parent_role="Female", ratio_value=4,
				item_code="B53/B50", quantity_per_hectare=20, uom="Kg",
				source_warehouse="Seed Stores", recovery_policy="Fully Recoverable",
				recoverable_percent=100,
			),
			SimpleNamespace(
				ratio_group="Primary", parent_role="Male", ratio_value=1,
				item_code="Z36", quantity_per_hectare=5, uom="Kg",
				source_warehouse="Seed Stores", recovery_policy="Fully Recoverable",
				recoverable_percent=100,
			),
		])
		get_conversion.side_effect = lambda item_code, uom: SimpleNamespace(
			uom=uom, stock_uom="Kg", conversion_factor=1
		)
		targets = [
			SimpleNamespace(crop_recipe="Bazooka Irindimura", target_hectares=hectares)
			for hectares in (5, 7)
		]

		rows = aggregate_parent_seed_requirements(targets)

		by_role = {row["parent_role"]: row for row in rows}
		self.assertEqual(by_role["Female"]["target_hectares"], 12)
		self.assertEqual(by_role["Female"]["required_stock_qty"], 240)
		self.assertEqual(by_role["Male"]["required_stock_qty"], 60)
		self.assertEqual(by_role["Female"]["ratio_value"], 4)
