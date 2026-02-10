# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CropRecipe(Document):
	def validate(self):
		stage_index = {}
		stage_name_by_row = {}
		for s in self.stages or []:
			if s.stage_name:
				stage_index[s.stage_name] = s.order_index or s.idx
			if s.name and s.stage_name:
				stage_name_by_row[s.name] = s.stage_name

		for row in self.inputs or []:
			# Migrate old rowname link to stage name if needed
			if row.recipe_stage in stage_name_by_row:
				row.recipe_stage = stage_name_by_row.get(row.recipe_stage)

			# Default recipe_stage from input_type if missing
			if not row.recipe_stage and row.input_type in stage_index:
				row.recipe_stage = row.input_type

			if row.recipe_stage in stage_index:
				row.stage_index = stage_index.get(row.recipe_stage)
