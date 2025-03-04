from __future__ import annotations

import logging
import pathlib
from typing import List, Any, Optional, Dict, TYPE_CHECKING

from ..menu.menu import MenuSelectionType
from ..menu.text_input import TextInput

from ..locale_helpers import list_keyboard_languages, list_timezones
from ..menu import Menu
from ..output import log
from ..profiles import Profile, list_profiles
from ..mirrors import list_mirrors

from ..translationhandler import Language
from ..packages.packages import validate_package_list

from ..storage import storage

if TYPE_CHECKING:
	_: Any


def ask_ntp(preset: bool = True) -> bool:
	prompt = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n'))
	prompt += str(_('Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki'))
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()
	choice = Menu(prompt, Menu.yes_no(), skip=False, preset_values=preset_val, default_option=Menu.yes()).run()

	return False if choice.value == Menu.no() else True


def ask_hostname(preset: str = None) -> str:
	hostname = TextInput(_('Desired hostname for the installation: '), preset).run().strip(' ')
	return hostname


def ask_for_a_timezone(preset: str = None) -> str:
	timezones = list_timezones()
	default = 'UTC'

	choice = Menu(
		_('Select a timezone'),
		list(timezones),
		preset_values=preset,
		default_option=default
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return choice.value


def ask_for_audio_selection(desktop: bool = True, preset: str = None) -> str:
	no_audio = str(_('No audio server'))
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', no_audio]
	default = 'pipewire' if desktop else no_audio

	choice = Menu(_('Choose an audio server'), choices, preset_values=preset, default_option=default).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return choice.value


def select_language(preset_value: str = None) -> str:
	"""
	Asks the user to select a language
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(sorted(list(kb_lang)), key=len)

	selected_lang = Menu(
		_('Select keyboard layout'),
		sorted_kb_lang,
		preset_values=preset_value,
		sort=False
	).run()

	if selected_lang.value is None:
		return preset_value

	return selected_lang.value


def select_mirror_regions(preset_values: Dict[str, Any] = {}) -> Dict[str, Any]:
	"""
	Asks the user to select a mirror or region
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""
	if preset_values is None:
		preselected = None
	else:
		preselected = list(preset_values.keys())
	mirrors = list_mirrors()
	selected_mirror = Menu(
		_('Select one of the regions to download packages from'),
		list(mirrors.keys()),
		preset_values=preselected,
		multi=True,
		raise_error_on_interrupt=True
	).run()

	match selected_mirror.type_:
		case MenuSelectionType.Ctrl_c: return {}
		case MenuSelectionType.Esc: return preset_values
		case _: return {selected: mirrors[selected] for selected in selected_mirror.value}


def select_archinstall_language(languages: List[Language], preset_value: Language) -> Language:
	# these are the displayed language names which can either be
	# the english name of a language or, if present, the
	# name of the language in its own language
	options = {lang.display_name: lang for lang in languages}

	choice = Menu(
		_('Archinstall language'),
		list(options.keys()),
		default_option=preset_value.display_name
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset_value
		case MenuSelectionType.Selection:
			return options[choice.value]


def select_profile(preset) -> Optional[Profile]:
	"""
	# Asks the user to select a profile from the available profiles.
	#
	# :return: The name/dictionary key of the selected profile
	# :rtype: str
	# """
	top_level_profiles = sorted(list(list_profiles(filter_top_level_profiles=True)))
	options = {}

	for profile in top_level_profiles:
		profile = Profile(None, profile)
		description = profile.get_profile_description()

		option = f'{profile.profile}: {description}'
		options[option] = profile

	title = _('This is a list of pre-programmed profiles, they might make it easier to install things like desktop environments')
	warning = str(_('Are you sure you want to reset this setting?'))

	selection = Menu(
		title=title,
		p_options=list(options.keys()),
		raise_error_on_interrupt=True,
		raise_error_warning_msg=warning
	).run()

	match selection.type_:
		case MenuSelectionType.Selection:
			return options[selection.value] if selection.value is not None else None
		case MenuSelectionType.Ctrl_c:
			storage['profile_minimal'] = False
			storage['_selected_servers'] = []
			storage['_desktop_profile'] = None
			storage['arguments']['desktop-environment'] = None
			storage['arguments']['gfx_driver_packages'] = None
			return None
		case MenuSelectionType.Esc:
			return None


def ask_additional_packages_to_install(pre_set_packages: List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	print(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.'))
	print(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.'))

	def read_packages(already_defined: list = []) -> list:
		display = ' '.join(already_defined)
		input_packages = TextInput(_('Write additional packages to install (space separated, leave blank to skip): '), display).run().strip()
		return input_packages.split() if input_packages else []

	pre_set_packages = pre_set_packages if pre_set_packages else []
	packages = read_packages(pre_set_packages)

	if not storage['arguments']['offline'] and not storage['arguments']['no_pkg_lookups']:
		while True:
			if len(packages):
				# Verify packages that were given
				print(_("Verifying that additional packages exist (this might take a few seconds)"))
				valid, invalid = validate_package_list(packages)

				if invalid:
					log(f"Some packages could not be found in the repository: {invalid}", level=logging.WARNING, fg='red')
					packages = read_packages(valid)
					continue
			break

	return packages

def add_number_of_parrallel_downloads(input_number :Optional[int] = None) -> Optional[int]:
	print(_("Enter the number of parallel downloads to be enabled.\n [Default value is 0]"))

	while input_number is None:
		try:
			input_number = int(TextInput("> ").run().strip() or 0)
			break
		except:
			print(_("Invalid input! Try again with a valid input"))

	pacman_conf_path = pathlib.Path("/etc/pacman.conf")
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split("\n")

	with pacman_conf_path.open("w") as fwrite:
		for line in pacman_conf:
			if "ParallelDownloads" in line:
				fwrite.write(f"ParallelDownloads = {input_number}\n")
			else:
				fwrite.write(f"{line}\n")

	return input_number


def select_additional_repositories(preset: List[str]) -> List[str]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: string
	"""

	repositories = ["multilib", "testing"]

	choice = Menu(
		_('Choose which optional additional repositories to enable'),
		repositories,
		sort=False,
		multi=True,
		preset_values=preset,
		raise_error_on_interrupt=True
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Ctrl_c: return []
		case MenuSelectionType.Selection: return choice.value
