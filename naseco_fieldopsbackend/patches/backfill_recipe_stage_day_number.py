import frappe


def execute():
	if not frappe.db.has_column("Recipe Stage", "day_number"):
		return
	frappe.db.sql(
		"""
		update `tabRecipe Stage`
		set day_number = case
			when start_day_offset = 0 and end_day_offset = 0 then 'Day 1'
			else concat('Day ', cast(end_day_offset as char))
		end
		where start_day_offset is not null
		  and end_day_offset is not null
		  and end_day_offset >= start_day_offset
		"""
	)
