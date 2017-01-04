# ST2 uses Python 2.6 and ST3 uses Python 3.3.
import sublime, sublime_plugin, re, os, sys, json
PYTHON_VERSION = sys.version_info

REGEX_CLASS_NAME = re.compile(r"<div class=\"title\">(.+?) class reference</div>", re.IGNORECASE)
REGEX_NAMESPACE_NAME = re.compile(r"<div class=\"title\">(.+?) namespace reference</div>", re.IGNORECASE)
REGEX_INHERITES_FROM = re.compile(r"inherited from <a.+?>(.+?)</a>", re.IGNORECASE)
REGEX_FUNCTION_SIGNATURE = re.compile(r"(?:<td class=\"memitemleft\".+?>(?P<returns>.+?))?&#.+?;</td><td class=\"memitemright\".+?><a.+?>(?P<name>.+?)</a>\s+\((?P<parameters>.+?)?\)", re.IGNORECASE)
REGEX_FUNCTION_RETURNS = re.compile(r"(?:(?P<const>const)\s*)?(?:(?P<static>static)\s*)?(?:<a.+?>(?P<type1>.+?)</a>|(?P<type2>[a-z:]+))(?:\s+&amp;)?", re.IGNORECASE)
REGEX_FUNCTION_PARAMETER = re.compile(r"(?:<a.+?>(?P<type1>[a-z:]+)</a>|(?P<type2>[a-z:]+))\s+(?P<name>[a-z]+)", re.IGNORECASE)
REGEX_ATTRIBUTE = re.compile(r"<td class=\"memitemleft\".+?>(?P<type>.+?)&#.+?;</td><td class=\"memitemright\".+?><a.+?>(?P<name>.+?)</a>", re.IGNORECASE)
REGEX_ATTRIBUTE_TYPE = re.compile(r"(?:(?P<const>const)\s*)?(?:(?P<static>static)\s*)?(?:<a.+?>(?P<type1>.+?)</a>|(?P<type2>[a-z:]+))(?:\s+&amp;)?", re.IGNORECASE)

def error_message(a_message):
	sublime.error_message("The Subliming of Isaac\n\n%s" % a_message)

class SublimingOfIsaacScrapeDocsCommand(sublime_plugin.WindowCommand):
	def run(self):
		settings = sublime.load_settings('The Subliming of Isaac.sublime-settings')
		if settings:
			path = settings.get("docs_path", None)
			if path and os.path.isdir(path):
				self.main(path)
			else:
				if not path:
					error_message("'docs_path' setting is undefined.")
				else:
					error_message("The value of the 'docs_path' setting is not a path to an existing directory.")

	def generate_completions(self, a_json):
		def function_completion(a_function, a_source):
			return_type = ""
			if a_function.get("returns", None):
				return_type = a_function["returns"].get("type", "")
			parameters = a_function.get("parameters", None)
			if parameters:
				i = 1
				temp = ""
				for parameter in parameters:
					if i > 1:
						temp = temp + ", "
					temp = temp + "${%d:%s %s}" % (i, parameter["type"], parameter["name"])
					i += 1
				parameters = temp
			else:
				parameters = ""
			if return_type:
				return {
					"trigger": "%s\t%s func. (%s)" % (a_function["name"].lower(), return_type, a_source),
					"contents": "%s(%s)" % (a_function["name"], parameters)
				}
			else:
				return {
					"trigger": "%s\tfunc. (%s)" % (a_function["name"].lower(), a_source),
					"contents": "%s(%s)" % (a_function["name"], parameters)
				}

		def attribute_completion(a_attribute, a_source):
			return {
				"trigger": "%s\t%s attr. (%s)" % (a_attribute["name"].lower(), a_attribute["type"], a_source),
				"contents": a_attribute["name"]
			}

		completions = []
		classes = a_json.get("classes", None)
		if classes:
			for class_key, class_ in classes.items():
				functions = class_.get("functions", None)
				if functions:
					for function_key, function in functions.items():
						completions.append(function_completion(function, "%s" % class_key))
				attributes = class_.get("attributes", None)
				if attributes:
					for attribute_key, attribute in attributes.items():
						completions.append(attribute_completion(attribute, "%s" % class_key))
		namespaces = a_json.get("namespaces", None)
		if namespaces:
			for namespace_key, namespace in namespaces.items():
				functions = namespace.get("functions", None)
				if functions:
					for function_key, function in functions.items():
						completions.append(function_completion(function, "%s" % namespace_key))
		if completions:
			return {"scope": "source.lua ", "completions": completions}
		return None

	def parse_class(self, a_path):
		class_name = None
		class_interface = {}
		lines = None
		with open(a_path, "r") as html_file:
			contents = html_file.read()
			class_name_match = REGEX_CLASS_NAME.search(contents)
			if class_name_match:
#				print("\nProcessing class:", class_name_match.group(1))
				class_name = class_name_match.group(1)
			inherits_from_match = REGEX_INHERITES_FROM.search(contents)
			if inherits_from_match:
				class_interface["inherits_from"] = inherits_from_match.group(1)
#				print("\tInherits from:", inherits_from_match.group(1))
			lines = contents.split("\n")
		class_functions = {}
		class_attributes = {}
		if lines:
			for line in lines:
				function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
				if function_signature_match:
#					print("\n\tReturns:", function_signature_match.group("returns"))
#					print("\tName:", function_signature_match.group("name"))
#					print("\tParameters:", function_signature_match.group("parameters"))
					function_signature = {}
					function_returns = function_signature_match.group("returns")
					if function_returns:
						function_returns_dict = {}
						function_returns_match = REGEX_FUNCTION_RETURNS.search(function_returns)
						if function_returns_match:
#							const = function_returns_match.group("const")
#							if const:
#								function_returns_dict["const"] = True
#							static = function_returns_match.group("static")
#							if static:
#								function_returns_dict["static"] = True
							return_type = function_returns_match.group("type1")
							if not return_type:
								return_type = function_returns_match.group("type2")
							function_returns_dict["type"] = return_type
							function_signature["returns"] = function_returns_dict
					function_name = function_signature_match.group("name")
					function_signature["name"] = function_name
					function_parameters = function_signature_match.group("parameters")
					if function_parameters:
						function_parameters_list = []
						function_parameters = function_parameters.split(", ")
						for parameter in function_parameters:
							parameter_match = REGEX_FUNCTION_PARAMETER.search(parameter)
							if parameter_match:
								parameter_type = parameter_match.group("type1")
								if not parameter_type:
									parameter_type = parameter_match.group("type2")
								parameter_name = parameter_match.group("name")
								function_parameters_list.append({"name": parameter_name, "type": parameter_type})
						function_signature["parameters"] = function_parameters_list
					class_functions[function_name] = function_signature
				else:
					attribute_signature_match = REGEX_ATTRIBUTE.search(line)
					if attribute_signature_match:
#						print("\tAttribute:", attribute_signature_match.groups())
						attribute_name = attribute_signature_match.group("name")
						attribute_type_match = REGEX_ATTRIBUTE_TYPE.search(attribute_signature_match.group("type"))
						if attribute_type_match:
							attribute = {"name": attribute_name}
#							const = attribute_type_match.group("const")
#							if const:
#								attribute["const"] = True
#							static = attribute_type_match.group("static")
#							if static:
#								attribute["static"] = True
							attribute_type = attribute_type_match.group("type1")
							if not attribute_type:
								attribute_type = attribute_type_match.group("type2")
							attribute["type"] = attribute_type
							if attribute:
								class_attributes[attribute_name] = attribute
		if class_functions:
			class_interface["functions"] = class_functions
		if class_attributes:
			class_interface["attributes"] = class_attributes
		if class_interface:
			class_interface["name"] = class_name
			return class_interface
		return None

	def parse_namespace(self, a_path):
		namespace_name = None
		namespace_interface = {}
		lines = None
		with open(a_path, "r") as html_file:
			contents = html_file.read()
			namespace_name_match = REGEX_NAMESPACE_NAME.search(contents)
			if namespace_name_match:
#				print("\nProcessing namespace:", namespace_name_match.group(1))
				namespace_name = namespace_name_match.group(1)
			lines = contents.split("\n")
		namespace_functions = {}
		if lines:
			for line in lines:
				function_signature_match = REGEX_FUNCTION_SIGNATURE.search(line)
				if function_signature_match:
#					print("\n\tReturns:", function_signature_match.group("returns"))
#					print("\tName:", function_signature_match.group("name"))
#					print("\tParameters:", function_signature_match.group("parameters"))
					function_signature = {}
					function_returns = function_signature_match.group("returns")
					if function_returns:
						function_returns_dict = {}
						function_returns_match = REGEX_FUNCTION_RETURNS.search(function_returns)
						if function_returns_match:
#							const = function_returns_match.group("const")
#							if const:
#								function_returns_dict["const"] = True
#							static = function_returns_match.group("static")
#							if static:
#								function_returns_dict["static"] = True
							return_type = function_returns_match.group("type1")
							if not return_type:
								return_type = function_returns_match.group("type2")
							function_returns_dict["type"] = return_type
							function_signature["returns"] = function_returns_dict
					function_name = function_signature_match.group("name")
					function_signature["name"] = function_name
					function_parameters = function_signature_match.group("parameters")
					if function_parameters:
						function_parameters_list = []
						function_parameters = function_parameters.split(", ")
						for parameter in function_parameters:
							parameter_match = REGEX_FUNCTION_PARAMETER.search(parameter)
							if parameter_match:
								parameter_type = parameter_match.group("type1")
								if not parameter_type:
									parameter_type = parameter_match.group("type2")
								parameter_name = parameter_match.group("name")
								function_parameters_list.append({"name": parameter_name, "type": parameter_type})
						function_signature["parameters"] = function_parameters_list
					namespace_functions[function_name] = function_signature
		if namespace_functions:
			namespace_interface["functions"] = namespace_functions
		if namespace_interface:
			namespace_interface["name"] = namespace_name
			return namespace_interface
		return None

	def main(self, a_path):
		classes_to_process = []
		namespaces_to_process = []
		for root, directory, files in os.walk(a_path):
			for file in files:
				if not "_1_1_" in file and file.startswith("class_") and file.endswith(".html") and not file.endswith("-members.html"):
					classes_to_process.append(file)
				elif file == "namespace_isaac.html":
					namespaces_to_process.append(file)
		scraped = {}
		if classes_to_process:
			classes = {}
			for class_ in classes_to_process:
				class_interface = self.parse_class(os.path.join(a_path, class_))
				if class_interface:
					classes[class_interface["name"]] = class_interface
			if classes:
				scraped["classes"] = classes
		if namespaces_to_process:
			namespaces = {}
			for namespace in namespaces_to_process:
				namespace_interface = self.parse_namespace(os.path.join(a_path, namespace))
				if namespace_interface:
					namespaces[namespace_interface["name"]] = namespace_interface
			if namespaces:
				scraped["namespaces"] = namespaces
		completions = self.generate_completions(scraped)
		if completions:
			with open(os.path.join(sublime.packages_path(), "User", "The Subliming of Isaac.sublime-completions"), "w") as f:
				json.dump(completions, f, indent=2)