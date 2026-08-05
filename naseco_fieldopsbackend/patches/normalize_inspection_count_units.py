from naseco_fieldopsbackend.patches.upgrade_inspection_sampling_protocol import (
	configure_parameters,
	configure_standards,
)


def execute():
	configure_parameters()
	configure_standards()
