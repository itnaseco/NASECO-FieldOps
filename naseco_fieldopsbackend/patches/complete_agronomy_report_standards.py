from naseco_fieldopsbackend.fixtures.seed_data import seed_agronomy_report_templates
from naseco_fieldopsbackend.patches.configure_agronomy_report_evaluation import (
	upgrade_open_reports,
)


def execute():
	seed_agronomy_report_templates()
	upgrade_open_reports()
