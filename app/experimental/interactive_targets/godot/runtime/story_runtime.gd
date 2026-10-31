extends RefCounted
## PoemSeed Studio B07 fixed typed-AST interpreter (target GODOT_4_RUNTIME_PROJECT_V1).
## The only program it runs is the bounded typed condition tree stored in data/story.json:
## bool/int literals and variables, eq/ne/lt/le/gt/ge comparisons, and/or/not, bounded
## assignments, node transitions, choice availability and an explicit step cap.
## There is no eval, no Expression, no dynamic code, no arbitrary resource loading.
## Every failure is returned as a code string; nothing is silently ignored.

const SAVE_SCHEMA := "poemseed-godot-save/1"
const SAVE_SCHEMA_VERSION := 1

var story: Dictionary = {}
var nodes: Dictionary = {}
var variable_defs: Dictionary = {}
var variables: Dictionary = {}
var entry_node_id := ""
var current_node_id := ""
var path: Array = []
var max_steps := 1
var status := "INVALID"
var valid := false
var error_detail := ""


func _init(story_data: Dictionary) -> void:
	story = story_data
	valid = false
	error_detail = ""
	nodes = {}
	variable_defs = {}
	variables = {}
	path = []
	var node_list = story.get("nodes", null)
	if typeof(node_list) != TYPE_ARRAY:
		error_detail = "NODES_INVALID"
		return
	for node in node_list:
		if typeof(node) != TYPE_DICTIONARY or not node.has("node_id"):
			error_detail = "NODE_INVALID"
			return
		nodes[str(node["node_id"])] = node
	var definition_list = story.get("variables", null)
	if typeof(definition_list) != TYPE_ARRAY:
		error_detail = "VARIABLES_INVALID"
		return
	for definition in definition_list:
		if typeof(definition) != TYPE_DICTIONARY or not definition.has("name"):
			error_detail = "VARIABLE_INVALID"
			return
		variable_defs[str(definition["name"])] = definition
	entry_node_id = str(story.get("entry_node_id", ""))
	max_steps = int(story.get("max_steps", 0))
	if not nodes.has(entry_node_id) or max_steps < 1:
		error_detail = "ENTRY_OR_STEP_CAP_INVALID"
		return
	valid = true
	_reset()


func is_valid() -> bool:
	return valid


func _reset() -> void:
	variables = {}
	for name in variable_defs:
		variables[name] = variable_defs[name]["initial"]
	path = []
	current_node_id = entry_node_id
	_refresh_status()


func _refresh_status() -> void:
	var node: Dictionary = nodes[current_node_id]
	if not str(node["ending"]).is_empty():
		status = "ENDING"
		return
	if path.size() >= max_steps:
		status = "STEP_CAP_REACHED"
		return
	for choice in node["choices"]:
		if _eval_bool(choice["condition"]):
			status = "PLAYING"
			return
	status = "NO_EXIT"


func current_state() -> Dictionary:
	_refresh_status()
	var node: Dictionary = nodes[current_node_id]
	var choices := []
	for choice in node["choices"]:
		choices.append({"id": str(choice["id"]), "label": str(choice["label"]),
			"enabled": _eval_bool(choice["condition"])})
	var node_state := {
		"node_id": str(node["node_id"]),
		"title": str(node["title"]),
		"dialogue": str(node["dialogue"]),
		"speaker": str(node["speaker"]),
		"ending": str(node["ending"]),
	}
	return {
		"node": node_state,
		"choices": choices,
		"variables": variables.duplicate(true),
		"steps": path.size(),
		"max_steps": max_steps,
		"status": status,
		"path": path.duplicate(),
	}


func advance(choice_id: String) -> Dictionary:
	if not valid:
		return {"ok": false, "error": "RUNTIME_INVALID"}
	if path.size() >= max_steps:
		return {"ok": false, "error": "STEP_CAP_REACHED"}
	_refresh_status()
	if status != "PLAYING":
		return {"ok": false, "error": "CHOICE_UNAVAILABLE"}
	var node: Dictionary = nodes[current_node_id]
	var selected := {}
	for candidate in node["choices"]:
		if str(candidate["id"]) == choice_id:
			selected = candidate
			break
	if selected.is_empty():
		return {"ok": false, "error": "CHOICE_UNAVAILABLE"}
	if not _eval_bool(selected["condition"]):
		return {"ok": false, "error": "CHOICE_DISABLED"}
	var pending := {}
	for name in selected["assignments"]:
		var definition: Dictionary = variable_defs[str(name)]
		var raw = selected["assignments"][name]
		if not _assignment_allowed(definition, raw):
			return {"ok": false, "error": "ASSIGNMENT_REJECTED"}
		pending[str(name)] = raw
	for name in pending:
		variables[name] = pending[name]
	path.append(choice_id)
	current_node_id = str(selected["target"])
	_refresh_status()
	return {"ok": true, "error": ""}


func snapshot() -> Dictionary:
	return {
		"schema": SAVE_SCHEMA,
		"save_schema_version": SAVE_SCHEMA_VERSION,
		"story": {
			"id": str(story["story_id"]),
			"revision": int(story["revision"]),
			"spec_digest": str(story["spec_digest"]),
			"source_digest": str(story["source_digest"]),
			"review_receipt": str(story["review_receipt"]),
		},
		"current_node_id": current_node_id,
		"path": path.duplicate(),
		"variables": variables.duplicate(true),
		"steps": path.size(),
	}


func restore(save: Dictionary) -> Dictionary:
	if not valid:
		return {"ok": false, "error": "RUNTIME_INVALID"}
	var identity = save.get("story", null)
	if typeof(identity) != TYPE_DICTIONARY:
		return {"ok": false, "error": "SAVE_STORY_INVALID"}
	if str(identity.get("id", "")) != str(story["story_id"]):
		return {"ok": false, "error": "SAVE_STORY_ID_MISMATCH"}
	var revision := SaveInt.strict(identity.get("revision", null))
	if not bool(revision["ok"]) or int(revision["value"]) != int(story["revision"]):
		return {"ok": false, "error": "SAVE_STORY_REVISION_MISMATCH"}
	if str(identity.get("spec_digest", "")) != str(story["spec_digest"]):
		return {"ok": false, "error": "SAVE_SPEC_DIGEST_MISMATCH"}
	if str(identity.get("source_digest", "")) != str(story["source_digest"]):
		return {"ok": false, "error": "SAVE_SOURCE_DIGEST_MISMATCH"}
	if str(identity.get("review_receipt", "")) != str(story["review_receipt"]):
		return {"ok": false, "error": "SAVE_REVIEW_RECEIPT_MISMATCH"}
	var saved_path = save.get("path", null)
	if typeof(saved_path) != TYPE_ARRAY or saved_path.size() > max_steps:
		return {"ok": false, "error": "SAVE_PATH_INVALID"}
	var saved_variables = save.get("variables", null)
	if typeof(saved_variables) != TYPE_DICTIONARY or saved_variables.size() != variable_defs.size():
		return {"ok": false, "error": "SAVE_VARIABLES_INVALID"}
	var coerced := {}
	for name in variable_defs:
		if not saved_variables.has(name):
			return {"ok": false, "error": "SAVE_VARIABLES_INVALID"}
		var definition: Dictionary = variable_defs[name]
		var raw = saved_variables[name]
		var typed := _coerce_saved_scalar(definition, raw)
		if not bool(typed["ok"]):
			return {"ok": false, "error": "SAVE_VARIABLES_INVALID"}
		coerced[str(name)] = typed["value"]
	var saved_steps := SaveInt.strict(save.get("steps", null))
	if not bool(saved_steps["ok"]) or int(saved_steps["value"]) != saved_path.size():
		return {"ok": false, "error": "SAVE_STEP_COUNT_MISMATCH"}
	_reset()
	for choice_id in saved_path:
		if typeof(choice_id) != TYPE_STRING:
			return {"ok": false, "error": "SAVE_PATH_INVALID"}
		var advanced: Dictionary = advance(str(choice_id))
		if not bool(advanced["ok"]):
			return {"ok": false, "error": "SAVE_REPLAY_REJECTED"}
	if current_node_id != str(save.get("current_node_id", "")):
		return {"ok": false, "error": "SAVE_STATE_MISMATCH"}
	if path.size() != int(saved_steps["value"]):
		return {"ok": false, "error": "SAVE_STATE_MISMATCH"}
	for name in coerced:
		if not _same_typed_value(coerced[name], variables[name]):
			return {"ok": false, "error": "SAVE_STATE_MISMATCH"}
	return {"ok": true, "error": ""}


func _coerce_saved_scalar(definition: Dictionary, raw) -> Dictionary:
	var kind := str(definition["type"])
	if kind == "bool":
		if typeof(raw) == TYPE_BOOL:
			return {"ok": true, "value": bool(raw)}
		return {"ok": false, "value": null}
	var typed := SaveInt.strict(raw)
	if not bool(typed["ok"]):
		return {"ok": false, "value": null}
	var value := int(typed["value"])
	if value < int(definition["minimum"]) or value > int(definition["maximum"]):
		return {"ok": false, "value": null}
	return {"ok": true, "value": value}


func _same_typed_value(expected, actual) -> bool:
	if typeof(expected) != typeof(actual):
		return false
	return expected == actual


func _assignment_allowed(definition: Dictionary, raw) -> bool:
	var kind := str(definition["type"])
	if kind == "bool":
		return typeof(raw) == TYPE_BOOL
	if typeof(raw) != TYPE_INT:
		return false
	var value := int(raw)
	return value >= int(definition["minimum"]) and value <= int(definition["maximum"])


func _eval_bool(tree: Dictionary) -> bool:
	var value = _eval(tree)
	return value == true


func _eval(tree: Dictionary) -> Variant:
	var op := str(tree["op"])
	match op:
		"literal":
			return tree["value"]
		"var":
			return variables[str(tree["name"])]
		"not":
			return not _eval_bool(tree["arg"])
		"and":
			for arg in tree["args"]:
				if not _eval_bool(arg):
					return false
			return true
		"or":
			for arg in tree["args"]:
				if _eval_bool(arg):
					return true
			return false
		_:
			var left = _eval(tree["left"])
			var right = _eval(tree["right"])
			match op:
				"eq":
					return left == right
				"ne":
					return left != right
				"lt":
					return left < right
				"le":
					return left <= right
				"gt":
					return left > right
				"ge":
					return left >= right
	return false


class SaveInt:
	## Strict integer coercion for save data (JSON may decode integers as floats).
	static func strict(raw) -> Dictionary:
		if typeof(raw) == TYPE_INT:
			return {"ok": true, "value": int(raw)}
		if typeof(raw) == TYPE_FLOAT:
			var number := float(raw)
			if is_finite(number) and number == floor(number) and number >= -1000000000 and number <= 1000000000:
				return {"ok": true, "value": int(number)}
		return {"ok": false, "value": 0}
