import sys, sublime, os, json
PYTHON_VERSION = sys.version_info

def error_message(a_message):
	sublime.error_message("The Subliming of Isaac:\n\n%s" % a_message)

def debug_print(*a_message):
	print("DEBUG: ", a_message)

def read_resource_file(a_filename):
	path = os.path.join(sublime.packages_path(), "User", a_filename)
	if os.path.isfile(path):
		with open(path, "r") as file:
			return json.load(file)
	return None

def write_resource_file(a_filename, a_json):
	with open(os.path.join(sublime.packages_path(), "User", a_filename), "w") as file:
		json.dump(a_json, file, indent=4)
		return True
	return False

def load_afterbirth_api():
	api = read_resource_file("The Subliming of Isaac.json")
	if not api:
		error_message("Afterbirth+ API needs to be scraped.")
		return None
	return api

def read_file(a_path):
	with open(a_path, "r") as file:
		return file.read()
	return ""

def get_package_settings():
	return sublime.load_settings('The Subliming of Isaac.sublime-settings')