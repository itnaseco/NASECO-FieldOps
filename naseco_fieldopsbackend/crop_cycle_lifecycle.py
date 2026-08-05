# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

from dataclasses import dataclass


@dataclass(frozen=True)
class LifecycleStage:
	code: str
	name: str
	order: int
	start_day: int
	end_day: int
	report_number: int


LIFECYCLE_STAGES = (
	LifecycleStage("FIELD_VERIFICATION", "Field Verification & Contracting", 1, -30, -1, 1),
	LifecycleStage("PLANTING", "Planting", 2, 0, 0, 2),
	LifecycleStage("EMERGENCE", "Crop Emergence / Germination", 3, 7, 14, 3),
	LifecycleStage("VEGETATIVE", "Vegetative", 4, 25, 45, 4),
	LifecycleStage("PRE_FLOWERING", "Pre-flowering", 5, 46, 60, 5),
	LifecycleStage("FLOWERING", "Flowering", 6, 61, 75, 6),
	LifecycleStage("PRE_HARVEST", "Pre-harvest", 7, 120, 135, 7),
	LifecycleStage("HARVEST", "Harvest", 8, 150, 180, 8),
	LifecycleStage("DELIVERY", "Delivery", 9, 180, 190, 9),
)

STAGES_BY_NAME = {stage.name: stage for stage in LIFECYCLE_STAGES}
STAGES_BY_CODE = {stage.code: stage for stage in LIFECYCLE_STAGES}
STAGE_NAMES = tuple(stage.name for stage in LIFECYCLE_STAGES)

LEGACY_STAGE_MAP = {
	"Land Preparation": "Field Verification & Contracting",
	"Basal Fertilizer Application": "Planting",
	"First Weeding": "Vegetative",
	"Top Dressing": "Vegetative",
	"Second Weeding": "Pre-flowering",
	"Pest & Disease Control": "Vegetative",
	"Harvesting": "Harvest",
}


def canonical_stage_name(value):
	if not value:
		return None
	value = str(value).strip()
	return LEGACY_STAGE_MAP.get(value, value)


def get_stage(value):
	value = canonical_stage_name(value)
	return STAGES_BY_NAME.get(value) or STAGES_BY_CODE.get(value)
