import sys, sublime, sublime_plugin, os, json
from operator import itemgetter

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
	import SharedFunctions
elif PYTHON_VERSION[0] >= 3:
	from . import SharedFunctions
	from .SharedEnums import APIKeyEnum

DEFAULT_VALUE_NO_DESCRIPTION = "None"

API_LOADED = False

class SublimingOfIsaacBrowseDocumentationCommand(sublime_plugin.WindowCommand):
	def run(self):
		global API_LOADED
		if not API_LOADED:
			self.afterbirth_api = SharedFunctions.load_afterbirth_api()
			if not self.afterbirth_api:
				return
			API_LOADED = True
		items = []
		for key, item in self.afterbirth_api.items():
			items.append([key, "Browse dictionary", type(item)])
		self.keys_so_far = []
		self.items = self.sort_items(items)
		self.separate_types(self.items)
		self.window.show_quick_panel(self.items, self.on_select)

	def on_select(self, a_index):
		if a_index < 0:
			return

		def back_button():
			if self.keys_so_far:
				self.keys_so_far.pop()

		def node_position():
			if self.item_types[a_index] != str:
				key = self.items[a_index][0]
				key_count = len(self.keys_so_far)
				if key_count <= 0 or (key_count > 0 and self.keys_so_far[-1] != key):
					self.keys_so_far.append(key)

		def dict_node(a_node):
			items = []
			for key, item in a_node.items():
				if isinstance(item, dict):
					if key == APIKeyEnum.RETURNS:
						items.append([key, item.get(APIKeyEnum.TYPE, "<Type missing>"), type(item)])
					else:
						description = item.get(APIKeyEnum.DESCRIPTION, "Browse dictionary")
						if description and isinstance(description, str):
							items.append([key, description, type(item)])
						else:
							items.append([key, "Browse dictionary", type(item)])
				elif isinstance(item, list):
					items.append([key, "Browse list", type(item)])
				elif isinstance(item, str):
					items.append([key, item, type(item)])
			return self.sort_items(items)

		def list_node(a_node):
			items = []
			for item in node:
				if isinstance(item, dict):
					if key == APIKeyEnum.PARAMETERS:
						items.append([item.get(APIKeyEnum.NAME, "<Name missing>"), "Type: %s"
							% item.get(APIKeyEnum.TYPE, "<Type missing>"), type(item)])
					else:
						items.append([item.get(APIKeyEnum.NAME, "<Name missing>"), item.get(APIKeyEnum.DESCRIPTION,
							"Browse dictionary"), type(item)])
				elif isinstance(item, list):
					items.append([item, "Browse list", type(item)])
				elif isinstance(item, str):
					items.append([item, "", type(item)])
			return self.insert_options(items)

		key_count = len(self.keys_so_far)
		if key_count == 0:
			if a_index > 0:
				node_position()
		elif key_count == 1 or (key_count == 2 and self.keys_so_far[0] != APIKeyEnum.FUNCTIONS):
			if a_index == 0: # Back
				back_button()
			elif a_index == 1: # Show data in a view
				if not self.to_view():
					self.window.show_quick_panel(self.items, self.on_select)
				return
			elif a_index > 2:
				node_position()
		else:
			if a_index == 0: # Back
				back_button()
			elif a_index > 1:
				node_position()
		current_key = ""
		key_count = len(self.keys_so_far)
		if len(self.keys_so_far) > 0:
			current_key = self.keys_so_far[-1]
		node = self.afterbirth_api
		for key in self.keys_so_far:
			if isinstance(node, dict):
				next_node = node.get(key, None)
				if next_node:
					node = next_node
				else:
					SharedFunctions.error_message("Failed to access %s in the API."
						% (":".join(self.keys_so_far)))
					return
			else:
				self.keys_so_far.pop()
				self.window.show_quick_panel(self.items, self.on_select)
				return
		if isinstance(node, dict):
			self.items = dict_node(node)
		elif isinstance(node, list):
			self.items = list_node(node)
		elif isinstance(node, str):
			pass
		self.separate_types(self.items)
		self.window.show_quick_panel(self.items, self.on_select)

	def sort_items(self, a_list):
		result = sorted(a_list, key=itemgetter(0))
		result = self.insert_options(result)
		return result

	def insert_options(self, a_list):
		key_count = len(self.keys_so_far)
		node_position_index = 0
		if key_count > 0:
			a_list.insert(0, ["Back", "Go back to the previous menu.", str])
			node_position_index += 1
		if key_count == 1 or (key_count == 2 and self.keys_so_far[0] != APIKeyEnum.FUNCTIONS):
			a_list.insert(1, ["Show in a view", "Writes the data below to a new view.", str])
			node_position_index += 1
		node_position = ["..."]
		node_position.extend(self.keys_so_far[-2:])
		a_list.insert(node_position_index, [" > ".join(node_position),
			"==============================================================================", str])
		return a_list

	def separate_types(self, a_list):
		modified = [entry for entry in a_list if len(entry) > 2]
		if modified:
			self.item_types = [entry.pop() for entry in a_list]

	def to_view(self):
		contents = ""
		node = self.afterbirth_api
		if not self.keys_so_far:
			return False
		for key in self.keys_so_far:
			if isinstance(node, dict):
				next_node = node.get(key, None)
				if next_node and isinstance(next_node, dict):
					node = next_node
				else:
					break
		title = ""
		key_count = len(self.keys_so_far)
		def get_functions(a_dict):
			functions = []
			constructor = None
			for function_name, function in a_dict.items():
				return_type = ""
				if function.get(APIKeyEnum.RETURNS, None):
					return_type = ""
					if function[APIKeyEnum.RETURNS].get(APIKeyEnum.STATIC, False):
						return_type = "static "
					if function[APIKeyEnum.RETURNS].get(APIKeyEnum.CONST, False):
						return_type = "const %s" % return_type
					return_type = "%s%s " % (return_type, function[APIKeyEnum.RETURNS].get(APIKeyEnum.TYPE,
						"<Type missing>"))
				function_parameters = function.get(APIKeyEnum.PARAMETERS, [])
				if function_parameters:
					function_parameters = ["%s %s" % (param[APIKeyEnum.TYPE], param[APIKeyEnum.NAME])
					for param in function_parameters]
					function_parameters = [param.strip() for param in function_parameters]
				function_signature = "%s%s(%s)" % (return_type, function_name,
					", ".join(function_parameters))
				if not constructor and function.get(APIKeyEnum.IS_CONSTRUCTOR, False):
					constructor = [function_name, function_signature, "Constructor - Description: %s"
						% function.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION)]
				else:
					functions.append([function_name, function_signature, "Description: %s"
						% function.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION)])
			functions = sorted(functions, key=itemgetter(0))
			if constructor:
				functions.insert(0, constructor)
			functions = [function[1:] for function in functions]
			return functions

		if self.keys_so_far[0] == APIKeyEnum.CLASSES:
			def get_class_attributes(a_dict):
				attributes = []
				for attribute_name, attribute in a_dict.items():
					type_ = ""
					if attribute.get(APIKeyEnum.STATIC, False):
						type_ = "static "
					if attribute.get(APIKeyEnum.CONST, False):
						type_ = "const %s" % type_
					type_ = "%s%s" % (type_, attribute.get(APIKeyEnum.TYPE, "<Type missing>"))
					attributes.append([attribute_name, "%s %s" % (type_.strip(), attribute_name),
						"Description: %s" % attribute.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION)])
				attributes = sorted(attributes, key=itemgetter(0))
				attributes = [attribute[1:] for attribute in attributes]
				return attributes

			if key_count == 2: # Specific class
				title = "%s class" % self.keys_so_far[1]
				if node.get(APIKeyEnum.INHERITS_FROM, None):
					title = "%s inherits from %s class" % (title, node[APIKeyEnum.INHERITS_FROM])
				if key_count > 2:
					if self.keys_so_far[2] == APIKeyEnum.FUNCTIONS: # Functions
						title = "%s functions" % title
						function_strings = get_functions(node)
						contents = "\nFunctions:\n\t%s" % "\n\n\t".join(["\n\t".join(function)
							for function in function_strings])
					elif self.keys_so_far[2] == APIKeyEnum.ATTRIBUTES: # Attributes
						title = "%s attributes" % title
						attribute_strings =get_class_attributes(node)
						contents = "\nAttributes:\n\t%s" % "\n\n\t".join(["\n\t".join(attribute)
							for attribute in attribute_strings])
				else: # Class info (functions and attributes)
					function_strings = get_functions(node.get(APIKeyEnum.FUNCTIONS, {}))
					attribute_strings =get_class_attributes(node.get(APIKeyEnum.ATTRIBUTES, {}))
					functions = "No functions."
					if function_strings:
						functions = "Functions:\n\t%s" % "\n\n\t".join(["\n\t".join(function)
							for function in function_strings])
					attributes = "No attributes."
					if attribute_strings:
						attributes = "Attributes:\n\t%s" % "\n\n\t".join(["\n\t".join(attribute)
							for attribute in attribute_strings])
					contents = "%s\n\n%s\n\n%s" % ("Description: %s" % node.get(APIKeyEnum.DESCRIPTION,
						DEFAULT_VALUE_NO_DESCRIPTION), functions, attributes)
			elif key_count == 1: # All classes
				title = "Classes"
				classes = []
				for key, class_ in node.items():
					if isinstance(class_, dict):
						function_strings = get_functions(class_.get(APIKeyEnum.FUNCTIONS, {}))
						for function in function_strings:
							function[0] = "\t\t%s" % function[0]
							function[1] = "\t\t%s" % function[1]
						attribute_strings =get_class_attributes(class_.get(APIKeyEnum.ATTRIBUTES, {}))
						for attribute in attribute_strings:
							attribute[0] = "\t\t%s" % attribute[0]
							attribute[1] = "\t\t%s" % attribute[1]
						functions = "\tNo functions."
						if function_strings:
							functions = "\tFunctions:\n%s" % "\n\n".join(["\n".join(function)
								for function in function_strings])
						attributes = "\n\tNo attributes."
						if attribute_strings:
							attributes = "\n\tAttributes:\n%s" % "\n\n".join(["\n".join(attribute)
								for attribute in attribute_strings])
						name = "%s class" % key
						if class_.get(APIKeyEnum.INHERITS_FROM, None):
							name = "%s inherits from %s class" % (name, class_[APIKeyEnum.INHERITS_FROM])
						classes.append([name, "Description: %s\n"
							% class_.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION), functions,
							attributes])
				classes = sorted(classes, key=itemgetter(0))
				contents = "\n%s" % ("\n\n".join(["\n".join(class_) for class_ in classes]))
			else:
				return False
		elif self.keys_so_far[0] == APIKeyEnum.ENUMS:
			def get_enum_members(a_list):
				members = []
				for member in a_list:
					members.append(["%s enumerator" % member.get(APIKeyEnum.NAME, "<Member name missing>"),
						"Description: %s" % member.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION)])
				return members

			if key_count == 2: # Specific enum
				title = "%s enum" % self.keys_so_far[1]
				members_strings = get_enum_members(node.get(APIKeyEnum.MEMBERS, []))
				contents = "Description: %s\n\nMembers:\n\t%s\n" % (
					node.get(APIKeyEnum.DESCRIPTION, "None"),
					"\n\n\t".join(["\n\t".join(member) for member in members_strings]))
			elif key_count == 1: # All enums
				title = "Enums"
				enums = []
				for key, enum in node.items():
					if isinstance(enum, dict):
						members_strings = get_enum_members(enum.get(APIKeyEnum.MEMBERS, []))
						for member in members_strings:
							member[0] = "\t\t%s" % member[0]
							member[1] = "\t\t%s" % member[1]
						enums.append(["%s enum" % key, "Description: %s\n\n\tMembers:"
							% enum.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION),
							"\n\n".join(["\n".join(member) for member in members_strings])])
				enums = sorted(enums, key=itemgetter(0))
				contents = "\n%s" % ("\n\n".join(["\n".join(enum) for enum in enums]))
			else:
				return False
		elif self.keys_so_far[0] == APIKeyEnum.NAMESPACES:
			title = "Namespaces"
			if key_count == 2: # Specific namespace (functions)
				title = "%s namespace" % self.keys_so_far[1]
				function_strings = get_functions(node.get(APIKeyEnum.FUNCTIONS, {}))
				contents = "Description: %s\n\nFunctions:\n\t%s" % (node.get(APIKeyEnum.DESCRIPTION,
					DEFAULT_VALUE_NO_DESCRIPTION),
					"\n\n\t".join(["\n\t".join(function) for function in function_strings]))
			elif key_count == 1: # All namespaces
				title = "Namespaces"
				namespaces = []
				for key, namespace in node.items():
					if isinstance(namespace, dict):
						function_strings = get_functions(namespace.get(APIKeyEnum.FUNCTIONS, {}))
						for function in function_strings:
							function[0] = "\t\t%s" % function[0]
							function[1] = "\t\t%s" % function[1]
						namespaces.append(["%s namespace" % key, "Description: %s\n\n\tFunctions:"
							% namespace.get(APIKeyEnum.DESCRIPTION, DEFAULT_VALUE_NO_DESCRIPTION),
							"\n\n".join(["\n".join(function) for function in function_strings])])
				namespaces = sorted(namespaces, key=itemgetter(0))
				contents = "\n%s" % ("\n\n".join(["\n".join(namespace) for namespace in namespaces]))
			else:
				return False
		elif self.keys_so_far[0] == APIKeyEnum.FUNCTIONS:
			title = "Functions"
			function_strings = get_functions(node)
			contents = "\n%s" % "\n\n".join(["\n".join(function) for function in function_strings])
		else:
			contents = json.dumps(node, indent=4)
		if title:
			contents = "Afterbirth+ API - %s\n%s" % (title, contents)
		else:
			contents = "Afterbirth+ API\n%s" % (contents)
		self.window.active_view().run_command("subliming_of_isaac_write_documentation_to_view",
			{"text": contents, "tab_title": "Afterbirth+ API - %s" % title})
		return True

	def scrape_api(self, a_index):
		if a_index >= 0:
			self.window.run_command("subliming_of_isaac_scrape_docs")

class SublimingOfIsaacWriteDocumentationToViewCommand(sublime_plugin.TextCommand):
	def run(self, edit, **args):
		view = sublime.active_window().new_file()
		if PYTHON_VERSION[0] >= 3: #TODO: Figure out why the .tmLanguage is failing to parse in ST2.
			view.set_syntax_file("The Subliming of Isaac.tmLanguage")
		view.set_scratch(True)
		view.insert(edit, 0, args.get("text", ""))
		view.set_read_only(True)
		view.set_name(args.get("tab_title", "Afterbirth+ API"))