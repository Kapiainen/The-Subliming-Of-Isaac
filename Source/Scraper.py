# ST2 uses Python 2.6 and ST3 uses Python 3.3.
import sublime, sublime_plugin, re, os, sys, json
PYTHON_VERSION = sys.version_info

REGEX_CLASS_NAME = re.compile(r"<div class=\"title\">(.+?) class reference</div>", re.IGNORECASE)
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

KEY_CONST = "Const"
KEY_STATIC = "Static"
KEY_ATTRIBUTES = "Attributes"
KEY_CLASSES = "Classes"
KEY_DESCRIPTION = "Description"
KEY_ENUMS = "Enums"
KEY_FUNCTIONS = "Functions"
KEY_MEMBERS = "Members"
KEY_NAME = "Name"
KEY_NAMESPACES = "Namespaces"
KEY_PARAMETERS = "Parameters"
KEY_RETURNS = "Returns"
KEY_TYPE = "Type"
KEY_INHERITS_FROM = "Inherits from"

def error_message(a_message):
	sublime.error_message("The Subliming of Isaac\n\n%s" % a_message)

class SublimingOfIsaacScrapeDocsCommand(sublime_plugin.WindowCommand):
	def run(self):
		settings = sublime.load_settings('The Subliming of Isaac.sublime-settings')
		if settings:
			self.scope = settings.get("completions_scope", "source.lua")
			path = settings.get("docs_path", None)
			if path and os.path.isdir(path):
				self.main(path)
			else:
				if not path:
					error_message("'docs_path' setting is undefined.")
				else:
					error_message("The value of the 'docs_path' setting is not a path to an existing directory.")

	def main(self, a_path):
		classes_to_process = []
		namespaces_to_process = []
		enums = None
		for root, directory, files in os.walk(a_path):
			for file in files:
				if file.startswith("class_") and file.endswith(".html") and not file.endswith("-members.html"):
					classes_to_process.append(file)
				elif file == "namespace_isaac.html":
					namespaces_to_process.append(file)
				elif file == "group___enumerations.html":
					enums = self.parse_enums(os.path.join(a_path, file))
		scraped = {}
		if classes_to_process:
			classes = {}
			for class_ in classes_to_process:
				class_name, class_interface = self.parse_class(os.path.join(a_path, class_))
				if class_name and class_interface:
					classes[class_name] = class_interface
			if classes:
				scraped[KEY_CLASSES] = classes
			else:
				scraped[KEY_CLASSES] = {}
		if namespaces_to_process:
			namespaces = {}
			for namespace in namespaces_to_process:
				namespace_name, namespace_interface = self.parse_namespace(os.path.join(a_path, namespace))
				if namespace_name and namespace_interface:
					namespaces[namespace_name] = namespace_interface
			if namespaces:
				scraped[KEY_NAMESPACES] = namespaces
			else:
				scraped[KEY_NAMESPACES] = {}
		if enums:
			scraped[KEY_ENUMS] = enums
		else:
			scraped[KEY_ENUMS] = {}
		completions = self.generate_completions(scraped)
		if completions:
			with open(os.path.join(sublime.packages_path(), "User", "The Subliming of Isaac.sublime-completions"), "w") as f:
				json.dump(completions, f, indent=2)
		if scraped:
			with open(os.path.join(sublime.packages_path(), "User", "The Subliming of Isaac.json"), "w") as f:
				json.dump(scraped, f, indent=4)
		sublime.status_message("Finished scraping Afterbirth+ API...")

	def parse_class(self, a_path):
		class_name = None
		class_interface = {}
		lines = None
		with open(a_path, "r") as html_file:
			contents = html_file.read()
			class_name_match = REGEX_CLASS_NAME.search(contents)
			if class_name_match:
				class_name = class_name_match.group(1)
			inherits_from_match = REGEX_INHERITS_FROM.search(contents)
			if inherits_from_match:
				class_interface[KEY_INHERITS_FROM] = inherits_from_match.group(1)
			lines = contents.split("\n")
		class_functions = {}
		class_attributes = {}
		if lines:
			function = {}
			attribute = {}
			for line in lines:
				function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
				if function_signature_match:
					if function:
						class_functions[function[KEY_NAME]] = function
						del function[KEY_NAME]
					function = {}
					function_returns = function_signature_match.group("returns")
					if function_returns:
						function_returns = REGEX_HTML_TAG_REPLACER.sub("", function_returns)
						function_returns_dict = {}
						function_returns_match = REGEX_FUNCTION_RETURNS.search(function_returns)
						if function_returns_match:
							const = function_returns_match.group("const")
							if const:
								function_returns_dict[KEY_CONST] = True
							static = function_returns_match.group("static")
							if static:
								function_returns_dict[KEY_STATIC] = True
							return_type = function_returns_match.group("type")
							function_returns_dict[KEY_TYPE] = return_type
							function[KEY_RETURNS] = function_returns_dict
					function_name = function_signature_match.group("name")
					function[KEY_NAME] = function_name
					function_parameters = function_signature_match.group("parameters")
					if function_parameters:
						function_parameters_list = []
						function_parameters = REGEX_HTML_TAG_REPLACER.sub("", function_parameters)
						function_parameters = function_parameters.split(", ")
						for parameter in function_parameters:
							parameter_match = REGEX_FUNCTION_PARAMETER.search(parameter)
							if parameter_match:
								parameter_type = parameter_match.group("type")
								parameter_name = parameter_match.group("name")
								if not parameter_name:
									parameter_name = ""
								function_parameters_list.append({KEY_NAME: parameter_name, KEY_TYPE: parameter_type})
						function[KEY_PARAMETERS] = function_parameters_list
				else:
					attribute_signature_match = REGEX_ATTRIBUTE.search(line)
					if attribute_signature_match:
						attribute_name = attribute_signature_match.group("name")
						attribute_type_string = REGEX_HTML_TAG_REPLACER.sub("", attribute_signature_match.group("type"))
						attribute_type_match = REGEX_ATTRIBUTE_TYPE.search(attribute_type_string)
						if attribute_type_match:
							if attribute:
								class_attributes[attribute[KEY_NAME]] = attribute
								del attribute[KEY_NAME]
							attribute = {KEY_NAME: attribute_name}
							const = attribute_type_match.group("const")
							if const:
								attribute[KEY_CONST] = True
							static = attribute_type_match.group("static")
							if static:
								attribute[KEY_STATIC] = True
							attribute_type = attribute_type_match.group("type")
							attribute[KEY_TYPE] = attribute_type
					else:
						description_match = REGEX_DESCRIPTION.search(line)
						if description_match:
							description_string = description_match.group(1).strip()
							description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
							if function:
								function[KEY_DESCRIPTION] = description_string
							elif attribute:
								attribute[KEY_DESCRIPTION] = description_string
			if function:
				class_functions[function[KEY_NAME]] = function
				del function[KEY_NAME]
				function = None
			if attribute:
				class_attributes[attribute[KEY_NAME]] = attribute
				del attribute[KEY_NAME]
		if class_functions:
			class_interface[KEY_FUNCTIONS] = class_functions
		if class_attributes:
			class_interface[KEY_ATTRIBUTES] = class_attributes
		if class_name and class_interface:
			return class_name, class_interface
		return None, None

	def parse_namespace(self, a_path):
		namespace_name = None
		namespace_interface = {}
		lines = None
		with open(a_path, "r") as html_file:
			contents = html_file.read()
			namespace_name_match = REGEX_NAMESPACE_NAME.search(contents)
			if namespace_name_match:
				namespace_name = namespace_name_match.group(1)
			lines = contents.split("\n")
		namespace_functions = {}
		if lines:
			function = {}
			for line in lines:
				function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
				if function_signature_match:
					if function:
						namespace_functions[function[KEY_NAME]] = function
						del function[KEY_NAME]
					function = {}
					function_returns = function_signature_match.group("returns")
					if function_returns:
						function_returns = REGEX_HTML_TAG_REPLACER.sub("", function_returns)
						function_returns_dict = {}
						function_returns_match = REGEX_FUNCTION_RETURNS.search(function_returns)
						if function_returns_match:
							const = function_returns_match.group("const")
							if const:
								function_returns_dict[KEY_CONST] = True
							static = function_returns_match.group("static")
							if static:
								function_returns_dict[KEY_STATIC] = True
							return_type = function_returns_match.group("type")
							function_returns_dict[KEY_TYPE] = return_type
							function[KEY_RETURNS] = function_returns_dict
					function_name = function_signature_match.group("name")
					function[KEY_NAME] = function_name
					function_parameters = function_signature_match.group("parameters")
					if function_parameters:
						function_parameters_list = []
						function_parameters = REGEX_HTML_TAG_REPLACER.sub("", function_parameters)
						function_parameters = function_parameters.split(", ")
						for parameter in function_parameters:
							parameter_match = REGEX_FUNCTION_PARAMETER.search(parameter)
							if parameter_match:
								parameter_type = parameter_match.group("type")
								parameter_name = parameter_match.group("name")
								if not parameter_name:
									parameter_name = ""
								function_parameters_list.append({KEY_NAME: parameter_name, KEY_TYPE: parameter_type})
						function[KEY_PARAMETERS] = function_parameters_list
				else:
					description_match = REGEX_DESCRIPTION.search(line)
					if description_match:
						description_string = description_match.group(1).strip()
						description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
						if function:
							function[KEY_DESCRIPTION] = description_string
			if function:
				namespace_functions[function[KEY_NAME]] = function
				del function[KEY_NAME]
		if namespace_functions:
			namespace_interface[KEY_FUNCTIONS] = namespace_functions
		if namespace_name and namespace_interface:
			return namespace_name, namespace_interface
		return None, None

	def parse_enums(self, a_path):
		enums = {}
		lines = None
		with open(a_path, "r") as html_file:
			contents = html_file.read()
			lines = contents.split("\n")	
		if lines:
			enum_name = None
			enum_members = []
			for line in lines:
				match = REGEX_ENUM_NAME.search(line)
				if match:
					if enum_name:
						enums[enum_name] = {KEY_MEMBERS: enum_members}
						enum_members = []
					enum_name = match.group(1)
				else:
					match = REGEX_ENUM_MEMBER.search(line)
					if match:
						member = {KEY_NAME: match.group("name")}
						description_string = match.group("desc")
						if description_string:
							description_string = REGEX_HTML_TAG_REPLACER.sub("", description_string)
							member[KEY_DESCRIPTION] = description_string
						enum_members.append(member)
			if enum_members:
				enums[enum_name] = {KEY_MEMBERS: enum_members}
			return enums
		return None

	def generate_completions(self, a_json):
		def function_completion(a_function_key, a_function, a_source):
			return_type = ""
			if a_function.get(KEY_RETURNS, None):
				return_type = a_function[KEY_RETURNS].get(KEY_TYPE, "")
			parameters = a_function.get(KEY_PARAMETERS, None)
			if parameters:
				i = 1
				temp = ""
				for parameter in parameters:
					if i > 1:
						temp = temp + ", "
					temp = temp + "${%d:%s %s}" % (i, parameter[KEY_TYPE], parameter[KEY_NAME])
					i += 1
				parameters = temp
			else:
				parameters = ""
			if return_type:
				return {
					"trigger": "%s\t%s func. (%s)" % (a_function_key.lower(), return_type, a_source),
					"contents": "%s(%s)" % (a_function_key, parameters)
				}
			else:
				return {
					"trigger": "%s\tfunc. (%s)" % (a_function_key.lower(), a_source),
					"contents": "%s(%s)" % (a_function_key, parameters)
				}

		def attribute_completion(a_attribute_key, a_attribute, a_source):
			return {
				"trigger": "%s\t%s attr. (%s)" % (a_attribute_key.lower(), a_attribute[KEY_TYPE], a_source),
				"contents": a_attribute_key
			}

		completions = []
		classes = a_json.get(KEY_CLASSES, None)
		if classes:
			for class_key, class_ in classes.items():
				functions = class_.get(KEY_FUNCTIONS, None)
				if functions:
					for function_key, function in functions.items():
						completions.append(function_completion(function_key, function, class_key))
				attributes = class_.get(KEY_ATTRIBUTES, None)
				if attributes:
					for attribute_key, attribute in attributes.items():
						completions.append(attribute_completion(attribute_key, attribute, class_key))
		namespaces = a_json.get(KEY_NAMESPACES, None)
		if namespaces:
			for namespace_key, namespace in namespaces.items():
				functions = namespace.get(KEY_FUNCTIONS, None)
				if functions:
					for function_key, function in functions.items():
						completions.append(function_completion(function_key, function, namespace_key))
		enums = a_json.get(KEY_ENUMS, None)
		if enums:
			for enum_key, enum in enums.items():
				members = enum.get(KEY_MEMBERS, None)
				if members:
					for member in members:
						completions.append(
							{
								"trigger": "%s\tenum member (%s)" % (member[KEY_NAME].lower(), enum_key),
								"contents": "%s.%s" % (enum_key, member[KEY_NAME])
							}
						)
		if completions:
			return {"scope": self.scope, "completions": completions}
		return None