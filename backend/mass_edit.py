#-*- coding: utf-8 -*-

from typing import List


def mass_delete(volume_ids: List[int]) -> None:
	return

def mass_rename(volume_ids: List[int]) -> None:
	return

def mass_update(volume_ids: List[int]) -> None:
	return

def mass_search(volume_ids: List[int]) -> None:
	return

def mass_unzip(volume_ids: List[int]) -> None:
	return

def mass_unmonitor(volume_ids: List[int]) -> None:
	return

def mass_monitor(volume_ids: List[int]) -> None:
	return

action_to_func = {
	'delete': mass_delete,
	'rename': mass_rename,
	'update': mass_update,
	'search': mass_search,
	'unzip': mass_unzip,
	'unmonitor': mass_unmonitor,
	'monitor': mass_monitor
}
