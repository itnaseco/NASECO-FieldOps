# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

"""Deterministic parent-seed population and weight calculations.

Keep this module free of Frappe dependencies so the arithmetic can be tested
without a database. Persisted documents should snapshot every input returned by
``calculate_parent_requirement`` so later recipe or laboratory changes do not
rewrite historical requirements.
"""

from decimal import Decimal, ROUND_HALF_UP


SIX_PLACES = Decimal("0.000001")


def _decimal(value, label):
	try:
		return Decimal(str(value))
	except Exception as exc:
		raise ValueError(f"{label} must be numeric.") from exc


def calculate_parent_requirement(
	*,
	total_plants_per_hectare,
	parent_ratio,
	total_ratio,
	germination_percent,
	thousand_kernel_weight_g,
	area_hectares=1,
	allowance_percent=0,
):
	"""Return the reproducible requirement for one parent-seed component."""
	total_plants = _decimal(total_plants_per_hectare, "Total plants per hectare")
	ratio = _decimal(parent_ratio, "Parent ratio")
	ratio_total = _decimal(total_ratio, "Total ratio")
	germination = _decimal(germination_percent, "Germination percentage")
	kernel_weight = _decimal(thousand_kernel_weight_g, "Thousand-kernel weight")
	area = _decimal(area_hectares, "Area hectares")
	allowance = _decimal(allowance_percent, "Allowance percentage")

	if total_plants <= 0:
		raise ValueError("Total plants per hectare must be greater than zero.")
	if ratio <= 0 or ratio_total <= 0 or ratio > ratio_total:
		raise ValueError("Parent and total ratio values must be positive and internally consistent.")
	if germination <= 0 or germination > 100:
		raise ValueError("Germination percentage must be greater than zero and at most 100.")
	if kernel_weight <= 0:
		raise ValueError("Thousand-kernel weight must be greater than zero.")
	if area <= 0:
		raise ValueError("Area hectares must be greater than zero.")
	if allowance < 0:
		raise ValueError("Allowance percentage cannot be negative.")

	population_share = ratio / ratio_total
	expected_plants = total_plants * population_share
	required_kernels = expected_plants / (germination / Decimal("100"))
	base_kg_per_hectare = required_kernels * kernel_weight / Decimal("1000000")
	planned_kg_per_hectare = base_kg_per_hectare * (
		Decimal("1") + allowance / Decimal("100")
	)
	planned_quantity = planned_kg_per_hectare * area

	return {
		"population_percent": (population_share * Decimal("100")).quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
		"expected_plants_per_hectare": expected_plants.quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
		"required_kernels_per_hectare": required_kernels.quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
		"base_kg_per_hectare": base_kg_per_hectare.quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
		"planned_kg_per_hectare": planned_kg_per_hectare.quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
		"planned_quantity_kg": planned_quantity.quantize(SIX_PLACES, rounding=ROUND_HALF_UP),
	}
