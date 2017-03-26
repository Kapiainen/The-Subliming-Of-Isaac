# ST2 uses Python 2.6 and ST3 uses Python 3.3.
import sys, sublime, sublime_plugin, re, os, json
PYTHON_VERSION = sys.version_info
if PYTHON_VERSION[0] == 2:
	import imp
	shared_enums_module = os.path.join(os.getcwd(), "SharedEnums.py")
	imp.load_source("SharedEnums", shared_enums_module)
	del shared_enums_module
	shared_functions_module = os.path.join(os.getcwd(), "SharedFunctions.py")
	imp.load_source("SharedFunctions", shared_functions_module)
	del shared_functions_module
	from SharedEnums import APIKeyEnum
	from SharedEnums import CompletionKeyEnum
	import SharedFunctions
elif PYTHON_VERSION[0] >= 3:
	from .SharedEnums import APIKeyEnum
	from .SharedEnums import CompletionKeyEnum
	from . import SharedFunctions


REGEX_CLASS_NAME = re.compile(r"<div class=\"title\">(.+?) class reference</div>", re.IGNORECASE)
#REGEX_CLASS_NAME = re.compile(r"<div class=\"title\">(?:.+?::)*(.+?) class reference</div>", re.IGNORECASE)
REGEX_NAMESPACE_NAME = re.compile(r"<div class=\"title\">(.+?) namespace reference</div>", re.IGNORECASE)
REGEX_INHERITS_FROM = re.compile(r"inherited from <a.+?>(.+?)</a>", re.IGNORECASE)
REGEX_FUNCTION_SIGNATURE = re.compile(r"(?:<td class=\"memitemleft\".+?>(?P<returns>.+?))?&#.+?;</td><td class=\"memitemright\".+?><a.+?>(?P<name>.+?)</a>\s+\((?P<parameters>.+?)?\)", re.IGNORECASE)
REGEX_FUNCTION_RETURNS = re.compile(r"(?:(?:(?P<const>const)\s*)?(?:(?P<static>static)\s*)?)*(?:(?P<type>[_a-z][_a-z0-9]*(?:::[_a-z][_a-z0-9]*)*))(?:\s+&amp;)?", re.IGNORECASE)
REGEX_FUNCTION_PARAMETER = re.compile(r"(?P<type>([_a-z][_a-z0-9]*(?:::[_a-z][_a-z0-9]*)*))(?:\s+(?P<name>[_a-z][_a-z0-9]*))?", re.IGNORECASE)
REGEX_ATTRIBUTE = re.compile(r"<td class=\"memitemleft\".+?>(?P<type>.+?)&#.+?;</td><td class=\"memitemright\".+?><a.+?>(?P<name>.+?)</a>", re.IGNORECASE)
REGEX_ATTRIBUTE_TYPE = re.compile(r"(?:(?:(?P<const>const)\s*)?(?:(?P<static>static)\s*)?)*(?:(?P<type>[_a-z][_a-z0-9]*(?:::[_a-z][_a-z0-9]*)*))(?:\s+&amp;)?", re.IGNORECASE)
REGEX_ENUM_NAME = re.compile(r"<h2 class=\"memtitle\"><span class=\"permalink\">.+?</span>(.+?)</h2>", re.IGNORECASE)
REGEX_ENUM_MEMBER = re.compile(r"<td class=\"fieldname\"><a.+?</a>(?P<name>.+?)&#.+?<td class=\"fielddoc\">(?:<p>(?P<desc>.+?)</p>)?", re.IGNORECASE)
REGEX_DESCRIPTION = re.compile(r"<td class=\"mdescright\">(.+?)<a.+?</td>", re.IGNORECASE)
REGEX_HTML_TAG_REPLACER = re.compile(r"<.*?>")

def function_completion(a_function_key, a_function, a_source, a_constructor = False):
	"""
Takes the name of the function, the function dictionary, and the source (class or namespace that it belongs to).
Generates a dictionary that conforms to the standard used in .sublime-snippet and .sublime-completions files.
	"""
	return_type = ""
	if a_function.get(APIKeyEnum.RETURNS, None):
		return_type = a_function[APIKeyEnum.RETURNS].get(APIKeyEnum.TYPE, "")
	parameters = a_function.get(APIKeyEnum.PARAMETERS, None)
	if parameters:
		i = 1
		temp = ""
		for parameter in parameters:
			if i > 1:
				temp = temp + ", "
			temp = temp + "${%d:%s}" % (i, ("%s %s" % (parameter[APIKeyEnum.TYPE], parameter[APIKeyEnum.NAME])).strip())
			i += 1
		parameters = temp
	else:
		parameters = ""
	if return_type:
		if a_constructor:
			return {
				CompletionKeyEnum.TRIGGER: "%s\t%s constr. (%s)" % (a_function_key.lower(), return_type, a_source),
				CompletionKeyEnum.CONTENTS: "%s(%s)" % (a_function_key, parameters)
			}
		else:
			return {
				CompletionKeyEnum.TRIGGER: "%s\t%s func. (%s)" % (a_function_key.lower(), return_type, a_source),
				CompletionKeyEnum.CONTENTS: "%s(%s)" % (a_function_key, parameters)
			}
	else:
		if a_constructor:
			return {
				CompletionKeyEnum.TRIGGER: "%s\tconstr. (%s)" % (a_function_key.lower(), a_source),
				CompletionKeyEnum.CONTENTS: "%s(%s)" % (a_function_key, parameters)
			}
		else:
			return {
				CompletionKeyEnum.TRIGGER: "%s\tfunc. (%s)" % (a_function_key.lower(), a_source),
				CompletionKeyEnum.CONTENTS: "%s(%s)" % (a_function_key, parameters)
			}

def attribute_completion(a_attribute_key, a_attribute, a_source):
	"""
Takes the name of the attribute, attribute dictionary, and the source (class that it belongs to).
Generates a dictionary that conforms to the standard used in .sublime-snippet and .sublime-completions files.
	"""
	return {
		CompletionKeyEnum.TRIGGER: "%s\t%s attr. (%s)" % (a_attribute_key.lower(),
			a_attribute[APIKeyEnum.TYPE], a_source),
		CompletionKeyEnum.CONTENTS: a_attribute_key
	}

def enum_completion(a_enumerator_key, a_enumerator, a_source):
	"""
Takes the name of the enumerator, the enumerator name, and the source (class or namespace it belongs to).
Generates a dictionary that conforms to the standard used in .sublime-snippet and .sublime-completions files.
	"""
	return {
		CompletionKeyEnum.TRIGGER: "%s\tenum member (%s)" % (a_enumerator_key, a_source),
		CompletionKeyEnum.CONTENTS: "%s.%s" % (a_source, a_enumerator)
	}

def get_class_name(a_contents):
	class_name_match = REGEX_CLASS_NAME.search(a_contents)
	if class_name_match:
		return class_name_match.group(1)
	return None

def get_class_parent(a_contents):
	inherits_from_match = REGEX_INHERITS_FROM.search(a_contents)
	if inherits_from_match:
		return inherits_from_match.group(1)
	return None

def get_function_return_type(a_function_signature_match):
	function_returns = a_function_signature_match.group("returns")
	function_returns_dict = {}
	if function_returns:
		function_returns = REGEX_HTML_TAG_REPLACER.sub("", function_returns)
		function_returns_match = REGEX_FUNCTION_RETURNS.search(function_returns)
		if function_returns_match:
			const = function_returns_match.group("const")
			if const:
				function_returns_dict[APIKeyEnum.CONST] = True
			static = function_returns_match.group("static")
			if static:
				function_returns_dict[APIKeyEnum.STATIC] = True
			return_type = function_returns_match.group("type")
			function_returns_dict[APIKeyEnum.TYPE] = return_type
	return function_returns_dict

def get_function_parameters(a_function_signature_match):
	function_parameters = a_function_signature_match.group("parameters")
	function_parameters_list = []
	if function_parameters:
		function_parameters = REGEX_HTML_TAG_REPLACER.sub("", function_parameters)
		function_parameters = function_parameters.split(", ")
		for parameter in function_parameters:
			parameter_match = REGEX_FUNCTION_PARAMETER.search(parameter)
			if parameter_match:
				parameter_type = parameter_match.group("type")
				parameter_name = parameter_match.group("name")
				if not parameter_name:
					parameter_name = ""
				function_parameters_list.append(
					{APIKeyEnum.NAME: parameter_name,
					APIKeyEnum.TYPE: parameter_type})
	return function_parameters_list

def parse_class(a_path):
	contents = SharedFunctions.read_file(a_path)
	class_name = get_class_name(contents)
	class_interface = {}
	class_interface[APIKeyEnum.INHERITS_FROM] = get_class_parent(contents)
	lines = contents.split("\n")
	if lines:
		class_functions = {}
		class_attributes = {}
		function = {}
		attribute = {}
		for line in lines:
			function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
			if function_signature_match: # Class function
				if function: # Descriptions are optional so finish processing any unfinished function.
					class_functions[function[APIKeyEnum.NAME]] = function
					del function[APIKeyEnum.NAME]
				function = {}
				function[APIKeyEnum.NAME] = function_signature_match.group("name")
				returns = get_function_return_type(function_signature_match)
				if returns:
					function[APIKeyEnum.RETURNS] = returns
				else:
					if function[APIKeyEnum.NAME] == class_name: # Class constructor
						function[APIKeyEnum.RETURNS] = {APIKeyEnum.TYPE: class_name}
						function[APIKeyEnum.IS_CONSTRUCTOR] = True
				parameters = get_function_parameters(function_signature_match)
				if parameters:
					function[APIKeyEnum.PARAMETERS] = parameters
			else:
				attribute_signature_match = REGEX_ATTRIBUTE.search(line)
				if attribute_signature_match: # Class attribute
					attribute_name = attribute_signature_match.group("name")
					attribute_type_string = REGEX_HTML_TAG_REPLACER.sub("",
						attribute_signature_match.group("type"))
					attribute_type_match = REGEX_ATTRIBUTE_TYPE.search(attribute_type_string)
					if attribute_type_match:
						if attribute: # Descriptions are optional so finish processing any unfinished attribute.
							class_attributes[attribute[APIKeyEnum.NAME]] = attribute
							del attribute[APIKeyEnum.NAME]
						attribute = {APIKeyEnum.NAME: attribute_name}
						const = attribute_type_match.group("const")
						if const:
							attribute[APIKeyEnum.CONST] = True
						static = attribute_type_match.group("static")
						if static:
							attribute[APIKeyEnum.STATIC] = True
						attribute_type = attribute_type_match.group("type")
						attribute[APIKeyEnum.TYPE] = attribute_type
				else:
					description_match = REGEX_DESCRIPTION.search(line)
					if description_match: # Function/attribute description
						description_string = description_match.group(1).strip()
						description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
						if function: # Add the description to the unfinished function.
							function[APIKeyEnum.DESCRIPTION] = description_string
						elif attribute: # Add the description to the unfinished attribute.
							attribute[APIKeyEnum.DESCRIPTION] = description_string

		if function: # Descriptions are optional so finish processing any unfinished function.
			class_functions[function[APIKeyEnum.NAME]] = function
			del function[APIKeyEnum.NAME]
			function = None
		if attribute: # Descriptions are optional so finish processing any unfinished attribute.
			class_attributes[attribute[APIKeyEnum.NAME]] = attribute
			del attribute[APIKeyEnum.NAME]

		if class_functions: # Add all processed functions to the class dict.
			class_interface[APIKeyEnum.FUNCTIONS] = class_functions
		if class_attributes: # Add all processed attributes to the class dict.
			class_interface[APIKeyEnum.ATTRIBUTES] = class_attributes
		if class_interface:
			return class_name, class_interface
	return None, None

def get_namespace_name(a_contents):
	namespace_name_match = REGEX_NAMESPACE_NAME.search(a_contents)
	if namespace_name_match:
		return namespace_name_match.group(1)
	return None

def parse_namespace(a_path):
	contents = SharedFunctions.read_file(a_path)
	namespace_name = get_namespace_name(contents)
	lines = contents.split("\n")
	if lines:
		namespace_interface = {}
		namespace_functions = {}
		function = {}
		for line in lines:
			function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
			if function_signature_match:
				if function:
					namespace_functions[function[APIKeyEnum.NAME]] = function
					del function[APIKeyEnum.NAME]
				function = {}
				function[APIKeyEnum.NAME] = function_signature_match.group("name")
				returns = get_function_return_type(function_signature_match)
				if returns:
					function[APIKeyEnum.RETURNS] = returns
				parameters = get_function_parameters(function_signature_match)
				if parameters:
					function[APIKeyEnum.PARAMETERS] = parameters
			else:
				description_match = REGEX_DESCRIPTION.search(line)
				if description_match:
					description_string = description_match.group(1).strip()
					description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
					if function:
						function[APIKeyEnum.DESCRIPTION] = description_string
		if function:
			namespace_functions[function[APIKeyEnum.NAME]] = function
			del function[APIKeyEnum.NAME]

		if namespace_functions:
			namespace_interface[APIKeyEnum.FUNCTIONS] = namespace_functions
		if namespace_name and namespace_interface:
			return namespace_name, namespace_interface
	return None, None

def parse_enums(a_path):
	enums = {}
	contents = SharedFunctions.read_file(a_path)
	lines = contents.split("\n")
	if lines:
		enum_name = None
		enum_members = []
		for line in lines:
			match = REGEX_ENUM_NAME.search(line)
			if match:
				if enum_name:
					enums[enum_name] = {APIKeyEnum.MEMBERS: enum_members}
					enum_members = []
				enum_name = match.group(1)
			else:
				match = REGEX_ENUM_MEMBER.search(line)
				if match:
					member = {APIKeyEnum.NAME: match.group("name")}
					description_string = match.group("desc")
					if description_string:
						description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
						member[APIKeyEnum.DESCRIPTION] = description_string
					enum_members.append(member)
		if enum_members:
			enums[enum_name] = {APIKeyEnum.MEMBERS: enum_members}
		return enums
	return None

def scrape_api(a_path):
	classes_to_process = []
	namespaces_to_process = []
	enums = None
	functions = None
	for root, directory, files in os.walk(a_path):
		for file in files:
			if file.startswith("class_") and file.endswith(".html") and not file.endswith("-members.html"):
				classes_to_process.append(file)
			elif file == "namespace_isaac.html":
				namespaces_to_process.append(file)
			elif file == "group__enums.html":
				enums = parse_enums(os.path.join(a_path, file))
			elif file == "group___functions.html":
				functions_name, functions = parse_class(os.path.join(a_path, file))
	scraped = {}
	if classes_to_process:
		classes = {}
		for class_ in classes_to_process:
			class_name, class_interface = parse_class(os.path.join(a_path, class_))
			if class_name and class_interface:
				classes[class_name] = class_interface
		if classes:
			scraped[APIKeyEnum.CLASSES] = classes
		else:
			scraped[APIKeyEnum.CLASSES] = {}
	if namespaces_to_process:
		namespaces = {}
		for namespace in namespaces_to_process:
			namespace_name, namespace_interface = parse_namespace(os.path.join(a_path, namespace))
			if namespace_name and namespace_interface:
				namespaces[namespace_name] = namespace_interface
		if namespaces:
			scraped[APIKeyEnum.NAMESPACES] = namespaces
		else:
			scraped[APIKeyEnum.NAMESPACES] = {}
	if enums:
		scraped[APIKeyEnum.ENUMS] = enums
	else:
		scraped[APIKeyEnum.ENUMS] = {}
	if functions:
		scraped[APIKeyEnum.FUNCTIONS] = functions[APIKeyEnum.FUNCTIONS]
	else:
		scraped[APIKeyEnum.FUNCTIONS] = {}
	return scraped

def generate_completions(a_json, a_scope):
	completions = []
	classes = a_json.get(APIKeyEnum.CLASSES, None)
	if classes:
		for class_key, class_ in classes.items():
			functions = class_.get(APIKeyEnum.FUNCTIONS, None)
			if functions:
				for function_key, function in functions.items():
					completions.append(function_completion(function_key, function, class_key,
						function.get(APIKeyEnum.IS_CONSTRUCTOR, False)))
			attributes = class_.get(APIKeyEnum.ATTRIBUTES, None)
			if attributes:
				for attribute_key, attribute in attributes.items():
					completions.append(attribute_completion(attribute_key, attribute, class_key))
	namespaces = a_json.get(APIKeyEnum.NAMESPACES, None)
	if namespaces:
		for namespace_key, namespace in namespaces.items():
			functions = namespace.get(APIKeyEnum.FUNCTIONS, None)
			if functions:
				for function_key, function in functions.items():
					completions.append(function_completion(function_key, function, namespace_key))
	enums = a_json.get(APIKeyEnum.ENUMS, None)
	if enums:
		for enum_key, enum in enums.items():
			members = enum.get(APIKeyEnum.MEMBERS, None)
			if members:
				for member in members:
					completions.append(enum_completion(member[APIKeyEnum.NAME].lower(),
						member[APIKeyEnum.NAME], enum_key))
	if completions:
		return {"scope": a_scope, "completions": completions}
	return None

class SublimingOfIsaacScrapeDocsCommand(sublime_plugin.WindowCommand):
	"""
Reads files in the official documentation for the Afterbirth+ Lua API and generates a JSON-formatted file
with information on classes, functions, attributes, enumerators, and namespaces described in the documentation.
Also generates static completions based on the information and generates a .sublime-completions file.
	"""
	def run(self):
		settings = SharedFunctions.get_package_settings()
		if settings:
			path = settings.get("docs_path", None)
			if path and os.path.isdir(path):
				scraped_api = scrape_api(path)
				if scraped_api:
					SharedFunctions.write_resource_file("The Subliming of Isaac.json", scraped_api)
					completions = generate_completions(scraped_api,
						settings.get("completions_scope", "source.lua"))
					if completions:
						SharedFunctions.write_resource_file("The Subliming of Isaac.sublime-completions",
							completions)
					sublime.status_message("Finished scraping Afterbirth+ API...")
			else:
				if not path:
					SharedFunctions.error_message("'docs_path' setting is undefined.")
				else:
					SharedFunctions.error_message(
						"The value of the 'docs_path' setting is not a path to an existing directory.")

	