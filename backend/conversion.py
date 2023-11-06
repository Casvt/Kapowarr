#-*- coding: utf-8 -*-

from typing import Dict, List
from os.path import splitext

from backend.converters import FileConverter

conversion_methods: Dict[str, Dict[str, FileConverter]] = {}
"source_format -> target_format -> conversion class"
for fc in FileConverter.__subclasses__():
	conversion_methods.setdefault(fc.source_format, {})[fc.target_format] = fc

def convert_file(file: str, formats: List[str]) -> str:
	"""Convert a file from one format to another.

	Args:
		file (str): The file to convert.
		formats (List[str]): A list of formats to convert the file to.
			Order of list is preference of format (left to right).
			
			Should be key `conversion.conversion_methods` -> source_format dict.

	Returns:
		str: The path of the converted file.
	"""
	source_format = splitext(file)[1].lstrip('.').lower()

	if not source_format in conversion_methods:
		return file

	available_formats = conversion_methods[source_format]
	for format in formats:
		if format in available_formats:
			conversion_class = available_formats[format]
			break
	else:
		return file
	
	return conversion_class().convert(file)

def preview_mass_convert(
	volume_id: int,
	issue_id: int = None
) -> List[Dict[str, str]]:
	return

def mass_convert(
	volume_id: int,
	files: List[str]
) -> None:
	return
