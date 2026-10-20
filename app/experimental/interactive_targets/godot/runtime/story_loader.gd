extends RefCounted
## PoemSeed Studio B07 fixed trusted story-data loader (target GODOT_4_RUNTIME_PROJECT_V1).
## Validates the typed JSON story contract without executing anything: no eval, no
## Expression, no dynamic code, no imports, no network. Only res://data/story.json is read.
## Numbers coming out of JSON are normalised to strict int/bool so the interpreter never
## compares a float against a typed integer variable.

const SCHEMA := "poemseed-godot-runtime-story/1"
const FORMAT_VERSION := "godot-runtime-story-1"
const TARGET_ID := "GODOT_4_RUNTIME_PROJECT_V1"

const MAX_FILE_BYTES := 2 * 1024 * 1024
const MAX_NODES := 100
const MAX_CHOICES := 8
const MAX_VARIABLES := 16
const MAX_STEPS := 128
const MAX_WITNESS := 100
const MAX_TITLE := 240
const MAX_DIALOGUE := 8000
const MAX_ENDING := 240
const MAX_SPEAKER := 2000
const MAX_LABEL := 240
const MAX_ASSIGNMENTS := 16
const MAX_TRIGGER_ASSIGNMENTS := 128
const MAX_WITNESS_STEPS := 128
const MAX_NAME := 32
const MAX_IDENTIFIER := 160
const MAX_AST_DEPTH := 12
const MAX_AST_BUDGET := 64
const MAX_SCALAR := 10000
const MAX_MEDIA_REFERENCES := 200

const TOP_LEVEL_KEYS := ["schema", "format_version", "engine_target", "story_id", "revision", "title",
	"spec_digest", "source_digest", "review_receipt", "entry_node_id", "max_steps", "variables", "nodes", "witness",
	"media_references"]
const NODE_KEYS := ["node_id", "title", "dialogue", "speaker", "ending", "choices"]
const CHOICE_KEYS := ["id", "label", "target", "condition", "assignments"]
const VARIABLE_KEYS := ["name", "type", "initial", "minimum", "maximum"]
const CONDITION_OPERATORS := ["literal", "var", "not", "and", "or", "eq", "ne", "lt", "le", "gt", "ge"]


static func load_file(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return _error("STORY_FILE_MISSING", path)
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("STORY_FILE_UNREADABLE", path)
	var size := file.get_length()
	if size <= 0 or size > MAX_FILE_BYTES:
		file.close()
		return _error("STORY_FILE_SIZE_INVALID", str(size))
	var text := file.get_as_text()
	file.close()
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return _error("STORY_JSON_INVALID", "top-level JSON value must be an object")
	return validate(parsed)


static func validate(data: Dictionary) -> Dictionary:
	for key in data:
		if not TOP_LEVEL_KEYS.has(str(key)):
			return _error("STORY_UNKNOWN_FIELD", str(key))
	if str(data.get("schema", "")) != SCHEMA:
		return _error("STORY_SCHEMA_INVALID", str(data.get("schema", "")))
	if str(data.get("format_version", "")) != FORMAT_VERSION:
		return _error("STORY_FORMAT_INVALID", str(data.get("format_version", "")))
	if str(data.get("engine_target", "")) != TARGET_ID:
		return _error("STORY_TARGET_INVALID", str(data.get("engine_target", "")))
	var story_id := str(data.get("story_id", ""))
	if not _bounded_identifier(story_id, 80):
		return _error("STORY_ID_INVALID", story_id)
	var revision := _strict_int(data.get("revision", null))
	if not bool(revision["ok"]) or int(revision["value"]) < 1 or int(revision["value"]) > 1000000000:
		return _error("STORY_REVISION_INVALID", "")
	var title: Variant = data.get("title", null)
	if typeof(title) != TYPE_STRING or str(title).length() < 1 or str(title).length() > MAX_TITLE or _has_control(str(title)):
		return _error("STORY_TITLE_INVALID", "")
	for key in ["spec_digest", "source_digest", "review_receipt"]:
		if not _valid_digest(data.get(key, null)):
			return _error("STORY_DIGEST_INVALID", key)
	var max_steps := _strict_int(data.get("max_steps", null))
	if not bool(max_steps["ok"]) or int(max_steps["value"]) < 1 or int(max_steps["value"]) > MAX_STEPS:
		return _error("STORY_MAX_STEPS_INVALID", "")
	var entry_node_id: Variant = data.get("entry_node_id", null)
	if typeof(entry_node_id) != TYPE_STRING or str(entry_node_id).length() < 1 or str(entry_node_id).length() > MAX_IDENTIFIER or _has_control(str(entry_node_id)):
		return _error("STORY_ENTRY_INVALID", "")
	var variables_result := _validate_variables(data.get("variables", null))
	if not bool(variables_result["ok"]):
		return _error(str(variables_result["error"]), str(variables_result["detail"]))
	var variables: Dictionary = variables_result["variables"]
	var nodes_result := _validate_nodes(data.get("nodes", null), variables)
	if not bool(nodes_result["ok"]):
		return _error(str(nodes_result["error"]), str(nodes_result["detail"]))
	var nodes: Array = nodes_result["nodes"]
	var node_ids := {}
	for node in nodes:
		node_ids[str(node["node_id"])] = true
	if not node_ids.has(str(entry_node_id)):
		return _error("STORY_ENTRY_MISSING", str(entry_node_id))
	for node in nodes:
		for choice in node["choices"]:
			if not node_ids.has(str(choice["target"])):
				return _error("STORY_TARGET_MISSING", str(node["node_id"]) + " -> " + str(choice["target"]))
	var witness_result := _validate_witness(data.get("witness", null), node_ids)
	if not bool(witness_result["ok"]):
		return _error(str(witness_result["error"]), str(witness_result["detail"]))
	var media_result := _validate_media(data.get("media_references", null), node_ids)
	if not bool(media_result["ok"]):
		return _error(str(media_result["error"]), str(media_result["detail"]))
	return {
		"ok": true, "error": "", "detail": "",
		"story": {
			"schema": SCHEMA,
			"format_version": FORMAT_VERSION,
			"engine_target": TARGET_ID,
			"story_id": story_id,
			"revision": int(revision["value"]),
			"title": str(title),
			"spec_digest": str(data["spec_digest"]),
			"source_digest": str(data["source_digest"]),
			"review_receipt": str(data["review_receipt"]),
			"entry_node_id": str(entry_node_id),
			"max_steps": int(max_steps["value"]),
			"variables": variables_result["definitions"],
			"nodes": nodes,
			"witness": witness_result["witness"],
			"media_references": media_result["references"],
		},
	}


static func _validate_variables(raw) -> Dictionary:
	if typeof(raw) != TYPE_ARRAY or raw.size() > MAX_VARIABLES:
		return _fail("STORY_VARIABLES_INVALID", "variables must be an array of at most 16 entries")
	var definitions := {}
	var ordered := []
	for item in raw:
		if typeof(item) != TYPE_DICTIONARY:
			return _fail("STORY_VARIABLE_INVALID", "variable entry must be an object")
		for key in item:
			if not VARIABLE_KEYS.has(str(key)):
				return _fail("STORY_VARIABLE_INVALID", "unknown variable field: " + str(key))
		var name := str(item.get("name", ""))
		if not _bounded_name(name):
			return _fail("STORY_VARIABLE_INVALID", "variable name is not a bounded lowercase identifier")
		if definitions.has(name):
			return _fail("STORY_VARIABLE_DUPLICATE", name)
		var kind := str(item.get("type", ""))
		if kind != "bool" and kind != "int":
			return _fail("STORY_VARIABLE_INVALID", name)
		var minimum := _strict_int(item.get("minimum", null))
		var maximum := _strict_int(item.get("maximum", null))
		if not bool(minimum["ok"]) or not bool(maximum["ok"]):
			return _fail("STORY_VARIABLE_INVALID", name)
		var low := int(minimum["value"])
		var high := int(maximum["value"])
		if low < -MAX_SCALAR or high > MAX_SCALAR or low > high:
			return _fail("STORY_VARIABLE_INVALID", name)
		var initial_result := _strict_scalar(item.get("initial", null), kind)
		if not bool(initial_result["ok"]):
			return _fail("STORY_VARIABLE_INVALID", name)
		var initial = initial_result["value"]
		if kind == "int" and (int(initial) < low or int(initial) > high):
			return _fail("STORY_VARIABLE_INVALID", name)
		var definition := {"name": name, "type": kind, "initial": initial, "minimum": low, "maximum": high}
		definitions[name] = definition
		ordered.append(definition)
	return {"ok": true, "error": "", "detail": "", "definitions": ordered, "variables": definitions}


static func _validate_nodes(raw, variables: Dictionary) -> Dictionary:
	if typeof(raw) != TYPE_ARRAY or raw.size() < 1 or raw.size() > MAX_NODES:
		return _fail("STORY_NODES_INVALID", "nodes must be an array of 1..100 entries")
	var node_ids := {}
	var nodes := []
	for item in raw:
		if typeof(item) != TYPE_DICTIONARY:
			return _fail("STORY_NODE_INVALID", "node entry must be an object")
		for key in item:
			if not NODE_KEYS.has(str(key)):
				return _fail("STORY_NODE_INVALID", "unknown node field: " + str(key))
		var node_id := str(item.get("node_id", ""))
		if node_id.length() < 1 or node_id.length() > MAX_IDENTIFIER or _has_control(node_id):
			return _fail("STORY_NODE_INVALID", "node_id is not a bounded plain string")
		if node_ids.has(node_id):
			return _fail("STORY_NODE_DUPLICATE", node_id)
		node_ids[node_id] = true
		var title: Variant = item.get("title", null)
		if typeof(title) != TYPE_STRING or str(title).length() < 1 or str(title).length() > MAX_TITLE or _has_forbidden_control(str(title)):
			return _fail("STORY_NODE_INVALID", node_id + ": title invalid")
		var dialogue: Variant = item.get("dialogue", null)
		if typeof(dialogue) != TYPE_STRING or str(dialogue).length() > MAX_DIALOGUE or _has_forbidden_control(str(dialogue)):
			return _fail("STORY_NODE_INVALID", node_id + ": dialogue invalid")
		var speaker: Variant = item.get("speaker", null)
		if typeof(speaker) != TYPE_STRING or str(speaker).length() > MAX_SPEAKER or _has_forbidden_control(str(speaker)):
			return _fail("STORY_NODE_INVALID", node_id + ": speaker invalid")
		var ending: Variant = item.get("ending", null)
		if typeof(ending) != TYPE_STRING or str(ending).length() > MAX_ENDING or _has_forbidden_control(str(ending)):
			return _fail("STORY_NODE_INVALID", node_id + ": ending invalid")
		var choices_result := _validate_choices(item.get("choices", null), variables, node_id)
		if not bool(choices_result["ok"]):
			return _fail(str(choices_result["error"]), str(choices_result["detail"]))
		var choices: Array = choices_result["choices"]
		if str(ending) != "" and choices.size() > 0:
			return _fail("STORY_NODE_INVALID", node_id + ": ending nodes cannot have choices")
		nodes.append({"node_id": node_id, "title": str(title), "dialogue": str(dialogue), "speaker": str(speaker),
			"ending": str(ending), "choices": choices})
	return {"ok": true, "error": "", "detail": "", "nodes": nodes, "node_ids": node_ids}


static func _validate_choices(raw, variables: Dictionary, node_id: String) -> Dictionary:
	if typeof(raw) != TYPE_ARRAY or raw.size() > MAX_CHOICES:
		return _fail("STORY_CHOICE_INVALID", node_id + ": choices must be an array of at most 8 entries")
	var choices := []
	var seen := {}
	for item in raw:
		if typeof(item) != TYPE_DICTIONARY:
			return _fail("STORY_CHOICE_INVALID", node_id + ": choice entry must be an object")
		for key in item:
			if not CHOICE_KEYS.has(str(key)):
				return _fail("STORY_CHOICE_INVALID", node_id + ": unknown choice field: " + str(key))
		var choice_id := str(item.get("id", ""))
		if not _bounded_name(choice_id):
			return _fail("STORY_CHOICE_INVALID", node_id + ": choice id invalid")
		if seen.has(choice_id):
			return _fail("STORY_CHOICE_INVALID", node_id + ": duplicate choice id")
		seen[choice_id] = true
		var label: Variant = item.get("label", null)
		if typeof(label) != TYPE_STRING or str(label).length() < 1 or str(label).length() > MAX_LABEL or _has_forbidden_control(str(label)):
			return _fail("STORY_CHOICE_INVALID", node_id + ": label invalid")
		var target: Variant = item.get("target", null)
		if typeof(target) != TYPE_STRING or str(target).length() < 1 or str(target).length() > MAX_IDENTIFIER or _has_control(str(target)):
			return _fail("STORY_CHOICE_INVALID", node_id + ": target invalid")
		var condition: Dictionary = item.get("condition", null)
		var budget := [MAX_AST_BUDGET]
		var condition_result := _condition_type(condition, variables, 0, budget)
		if not bool(condition_result["ok"]):
			return _fail(str(condition_result["error"]), node_id + "/" + choice_id + ": condition invalid")
		if str(condition_result["type"]) != "bool":
			return _fail("STORY_CONDITION_TYPE_INVALID", node_id + "/" + choice_id)
		var assignments_result := _validate_assignments(item.get("assignments", null), variables, node_id + "/" + choice_id)
		if not bool(assignments_result["ok"]):
			return _fail(str(assignments_result["error"]), str(assignments_result["detail"]))
		choices.append({"id": choice_id, "label": str(label), "target": str(target), "condition": condition,
			"assignments": assignments_result["assignments"]})
	return {"ok": true, "error": "", "detail": "", "choices": choices}


static func _validate_assignments(raw, variables: Dictionary, where: String) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY or raw.size() > MAX_ASSIGNMENTS:
		return _fail("STORY_ASSIGNMENT_INVALID", where + ": assignments must be an object of at most 16 entries")
	var assignments := {}
	for key in raw:
		var name := str(key)
		var definition = variables.get(name, null)
		if typeof(definition) != TYPE_DICTIONARY:
			return _fail("STORY_ASSIGNMENT_INVALID", where + ": unknown variable " + name)
		var typed := _strict_scalar(raw[key], str(definition["type"]))
		if not bool(typed["ok"]):
			return _fail("STORY_ASSIGNMENT_INVALID", where + ": assignment type mismatch for " + name)
		var value = typed["value"]
		if str(definition["type"]) == "int" and (int(value) < int(definition["minimum"]) or int(value) > int(definition["maximum"])):
			return _fail("STORY_ASSIGNMENT_OUT_OF_BOUNDS", where + ": " + name)
		assignments[name] = value
	return {"ok": true, "error": "", "detail": "", "assignments": assignments}


static func _validate_media(raw, node_ids: Dictionary) -> Dictionary:
	if typeof(raw) != TYPE_ARRAY or raw.size() > MAX_MEDIA_REFERENCES:
		return _fail("STORY_MEDIA_INVALID", "media_references must be an array of at most 200 records")
	var references := []
	for item in raw:
		if typeof(item) != TYPE_DICTIONARY:
			return _fail("STORY_MEDIA_INVALID", "media reference must be an object")
		for key in item:
			if key != "asset_id" and key != "kind" and key != "node_id":
				return _fail("STORY_MEDIA_INVALID", "unknown media reference field: " + str(key))
		var asset_id := str(item.get("asset_id", ""))
		if asset_id.length() < 1 or asset_id.length() > MAX_IDENTIFIER or _has_control(asset_id):
			return _fail("STORY_MEDIA_INVALID", "asset id invalid")
		var kind := str(item.get("kind", ""))
		if kind != "image" and kind != "audio":
			return _fail("STORY_MEDIA_INVALID", "media kind invalid")
		var node_id := str(item.get("node_id", ""))
		if not node_ids.has(node_id):
			return _fail("STORY_MEDIA_INVALID", "media reference node missing")
		references.append({"asset_id": asset_id, "kind": kind, "node_id": node_id})
	return {"ok": true, "error": "", "detail": "", "references": references}


static func _validate_witness(raw, node_ids: Dictionary) -> Dictionary:
	if typeof(raw) != TYPE_ARRAY or raw.size() > MAX_WITNESS:
		return _fail("STORY_WITNESS_INVALID", "witness must be an array of at most 100 authoritative ending records")
	var witness := []
	for item in raw:
		if typeof(item) != TYPE_DICTIONARY:
			return _fail("STORY_WITNESS_INVALID", "witness entry must be an object")
		var node_id := str(item.get("node_id", ""))
		if not node_ids.has(node_id):
			return _fail("STORY_WITNESS_INVALID", "witness node not in story")
		var ending: Variant = item.get("ending", null)
		if typeof(ending) != TYPE_STRING or str(ending).length() > MAX_ENDING:
			return _fail("STORY_WITNESS_INVALID", "witness ending invalid")
		var choices: Variant = item.get("choices", null)
		if typeof(choices) != TYPE_ARRAY or choices.size() > MAX_WITNESS_STEPS:
			return _fail("STORY_WITNESS_INVALID", "witness choices invalid")
		var path := []
		for choice_id in choices:
			if typeof(choice_id) != TYPE_STRING or not _bounded_name(str(choice_id)):
				return _fail("STORY_WITNESS_INVALID", "witness choice id invalid")
			path.append(str(choice_id))
		witness.append({"node_id": node_id, "ending": str(ending), "choices": path})
	return {"ok": true, "error": "", "detail": "", "witness": witness}


static func _condition_type(tree, variables: Dictionary, depth: int, budget: Array) -> Dictionary:
	if typeof(tree) != TYPE_DICTIONARY:
		return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
	budget[0] = int(budget[0]) - 1
	if int(budget[0]) < 0:
		return _cond_fail("STORY_CONDITION_TOO_COMPLEX")
	if depth > MAX_AST_DEPTH:
		return _cond_fail("STORY_CONDITION_NESTING_LIMIT")
	var op := str(tree.get("op", ""))
	if not CONDITION_OPERATORS.has(op):
		return _cond_fail("STORY_CONDITION_OPERATOR_UNSUPPORTED")
	if op == "literal":
		if tree.size() != 2 or not tree.has("value"):
			return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
		var value = tree["value"]
		if typeof(value) == TYPE_BOOL:
			return {"ok": true, "type": "bool", "error": ""}
		var typed := _strict_int(value)
		if not bool(typed["ok"]) or int(typed["value"]) < -MAX_SCALAR or int(typed["value"]) > MAX_SCALAR:
			return _cond_fail("STORY_CONDITION_LITERAL_INVALID")
		tree["value"] = int(typed["value"])
		return {"ok": true, "type": "int", "error": ""}
	if op == "var":
		if tree.size() != 2 or not tree.has("name"):
			return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
		var name := str(tree["name"])
		var definition = variables.get(name, null)
		if typeof(definition) != TYPE_DICTIONARY:
			return _cond_fail("STORY_CONDITION_UNDEFINED_VARIABLE")
		return {"ok": true, "type": str(definition["type"]), "error": ""}
	if op == "not":
		if tree.size() != 2 or not tree.has("arg"):
			return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
		var inner := _condition_type(tree["arg"], variables, depth + 1, budget)
		if not bool(inner["ok"]):
			return inner
		if str(inner["type"]) != "bool":
			return _cond_fail("STORY_CONDITION_TYPE_INVALID")
		return {"ok": true, "type": "bool", "error": ""}
	if op == "and" or op == "or":
		if tree.size() != 2 or not tree.has("args") or typeof(tree["args"]) != TYPE_ARRAY:
			return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
		var args: Array = tree["args"]
		if args.size() < 2 or args.size() > 64:
			return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
		for arg in args:
			var child := _condition_type(arg, variables, depth + 1, budget)
			if not bool(child["ok"]):
				return child
			if str(child["type"]) != "bool":
				return _cond_fail("STORY_CONDITION_TYPE_INVALID")
		return {"ok": true, "type": "bool", "error": ""}
	if tree.size() != 3 or not tree.has("left") or not tree.has("right"):
		return _cond_fail("STORY_CONDITION_SHAPE_INVALID")
	var left := _condition_type(tree["left"], variables, depth + 1, budget)
	if not bool(left["ok"]):
		return left
	var right := _condition_type(tree["right"], variables, depth + 1, budget)
	if not bool(right["ok"]):
		return right
	if str(left["type"]) != str(right["type"]):
		return _cond_fail("STORY_CONDITION_TYPE_INVALID")
	if op != "eq" and op != "ne" and str(left["type"]) != "int":
		return _cond_fail("STORY_CONDITION_TYPE_INVALID")
	return {"ok": true, "type": "bool", "error": ""}


static func _strict_int(raw) -> Dictionary:
	if typeof(raw) == TYPE_INT:
		return {"ok": true, "value": int(raw)}
	if typeof(raw) == TYPE_FLOAT:
		var number := float(raw)
		if is_finite(number) and number == floor(number) and number >= -1000000000 and number <= 1000000000:
			return {"ok": true, "value": int(number)}
	return {"ok": false, "value": 0}


static func _strict_scalar(raw, kind: String) -> Dictionary:
	if kind == "bool":
		if typeof(raw) == TYPE_BOOL:
			return {"ok": true, "value": bool(raw)}
		return {"ok": false, "value": null}
	var typed := _strict_int(raw)
	if not bool(typed["ok"]) or int(typed["value"]) < -MAX_SCALAR or int(typed["value"]) > MAX_SCALAR:
		return {"ok": false, "value": null}
	return {"ok": true, "value": int(typed["value"])}


static func _bounded_name(value: String) -> bool:
	if value.length() < 1 or value.length() > MAX_NAME:
		return false
	var first := value.unicode_at(0)
	if first < 97 or first > 122:
		return false
	for index in range(1, value.length()):
		var code := value.unicode_at(index)
		var lower := code >= 97 and code <= 122
		var digit := code >= 48 and code <= 57
		if not lower and not digit and code != 95:
			return false
	return true


static func _bounded_identifier(value: String, limit: int) -> bool:
	if value.length() < 1 or value.length() > limit:
		return false
	for index in range(value.length()):
		var code := value.unicode_at(index)
		var upper := code >= 65 and code <= 90
		var lower := code >= 97 and code <= 122
		var digit := code >= 48 and code <= 57
		if not upper and not lower and not digit and code != 95 and code != 45:
			return false
	return true


static func _valid_digest(raw) -> bool:
	if typeof(raw) != TYPE_STRING:
		return false
	var value := str(raw)
	if value.length() != 64:
		return false
	for index in range(64):
		var code := value.unicode_at(index)
		var digit := code >= 48 and code <= 57
		var lower := code >= 97 and code <= 102
		if not digit and not lower:
			return false
	return true


static func _has_forbidden_control(value: String) -> bool:
	for index in range(value.length()):
		var code := value.unicode_at(index)
		if code == 9 or code == 10 or code == 13:
			continue
		if code < 32 or code == 127:
			return true
	return false


static func _has_control(value: String) -> bool:
	for index in range(value.length()):
		var code := value.unicode_at(index)
		if code < 32 or code == 127:
			return true
	return false


static func _error(code: String, detail: String) -> Dictionary:
	return {"ok": false, "error": code, "detail": detail, "story": {}}


static func _fail(code: String, detail: String) -> Dictionary:
	return {"ok": false, "error": code, "detail": detail}


static func _cond_fail(code: String) -> Dictionary:
	return {"ok": false, "error": code, "type": "", "detail": ""}
