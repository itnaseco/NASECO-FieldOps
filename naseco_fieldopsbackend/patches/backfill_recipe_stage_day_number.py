import frappe


def execute():
	if not frappe.db.has_column("Recipe Stage", "day_number"):
		return
	frappe.db.sql(
		"""
		update `tabRecipe Stage`
		set day_number = case
			when start_day_offset < 0 then concat(
				cast(abs(start_day_offset) as char),
				case when abs(start_day_offset) = 1 then ' Day Prior' else ' Days Prior' end
			)
			when start_day_offset = 0 and end_day_offset = 0 then '1'
			else cast(end_day_offset as char)
		end
		where start_day_offset is not null
		  and end_day_offset is not null
		  and end_day_offset >= start_day_offset
		"""
	)
