extends RefCounted
## PoemSeed Studio B07 fixed controlled acceptance driver (target GODOT_4_RUNTIME_PROJECT_V1).
## Only active when explicit acceptance arguments follow the engine "--" separator. It
## emits deterministic one-line JSON records on stdout so an external verifier can align
## every step with the authoritative Python playback. It never reads arbitrary files and
## only writes the user:// JSON artefacts named on the command line.

const RESULT_SCHEMA := "poemseed-godot-runtime-result/1"
const STATE_PREFIX := "POEMSEED_STATE "

var _runtime = null
var _save_store = null


func _init(runtime, save_store_script) -> void:
	_runtime = runtime
	_save_store = save_store_script


static func wants_acceptance(user_args: PackedStringArray) -> bool:
	for arg in user_args:
		if arg == "--witness-path" or arg == "--load" or arg == "--save" or arg == "--result" or arg == "--print-user-dir":
			return true
	return false


static func parse_args(user_args: PackedStringArray) -> Dictionary:
	var options := {"ok": true, "error": "", "witness_path": [], "load": "", "save": "", "result": "", "print_user_dir": false}
	var index := 0
	while index < user_args.size():
		var arg: String = user_args[index]
		if arg == "--witness-path":
			if index + 1 >= user_args.size():
				return _option_error("MISSING_VALUE:witness-path")
			var split := _split_choice_path(user_args[index + 1])
			if not bool(split["ok"]):
				return _option_error("INVALID_CHOICE_PATH")
			options["witness_path"] = split["choices"]
			index += 2
		elif arg == "--load" or arg == "--save" or arg == "--result":
			if index + 1 >= user_args.size():
				return _option_error("MISSING_VALUE:" + arg.substr(2))
			options[arg.substr(2)] = user_args[index + 1]
			index += 2
		elif arg == "--print-user-dir":
			options["print_user_dir"] = true
			index += 1
		elif arg == "--":
			index += 1
		else:
			return _option_error("UNKNOWN_ARGUMENT:" + arg)
	return options


static func _option_error(detail: String) -> Dictionary:
	return {"ok": false, "error": detail, "witness_path": [], "load": "", "save": "", "result": "", "print_user_dir": false}


static func _split_choice_path(raw: String) -> Dictionary:
	if raw.is_empty():
		return {"ok": true, "choices": []}
	if raw.length() > 1024:
		return {"ok": false, "choices": []}
	var choices := []
	for part in raw.split(","):
		var choice_id: String = part
		if not _bounded_choice_id(choice_id):
			return {"ok": false, "choices": []}
		choices.append(choice_id)
	return {"ok": true, "choices": choices}


static func _bounded_choice_id(value: String) -> bool:
	if value.length() < 1 or value.length() > 32:
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


func run(user_args: PackedStringArray) -> int:
	print("POEMSEED_USERDIR " + ProjectSettings.globalize_path("user://"))
	print("POEMSEED_STORY " + JSON.stringify(_story_meta()))
	var options := parse_args(user_args)
	if not bool(options["ok"]):
		_emit_error("ACCEPTANCE_ARGUMENT_INVALID", str(options["error"]))
		return 3
	if not str(options["load"]).is_empty():
		var loaded: Dictionary = _save_store.read(str(options["load"]))
		if not bool(loaded["ok"]):
			_emit_error("SAVE_REJECTED", str(loaded["error"]))
			return 2
		var restored: Dictionary = _runtime.restore(loaded["save"])
		if not bool(restored["ok"]):
			_emit_error("SAVE_REJECTED", str(restored["error"]))
			return 2
		print("POEMSEED_RESTORED " + JSON.stringify({"steps": _runtime.path.size(), "current_node_id": _runtime.current_node_id}))
	_emit_state()
	for choice_id in options["witness_path"]:
		var advanced: Dictionary = _runtime.advance(str(choice_id))
		if not bool(advanced["ok"]):
			_emit_error("PATH_REJECTED", str(advanced["error"]))
			return 3
		_emit_state()
	if not str(options["save"]).is_empty():
		var saved: Dictionary = _save_store.write(str(options["save"]), _runtime.snapshot())
		if not bool(saved["ok"]):
			_emit_error("SAVE_WRITE_FAILED", str(saved["error"]))
			return 3
		print("POEMSEED_SAVED " + JSON.stringify({"path": str(options["save"]),
			"sha256": str(saved["sha256"]), "bytes": int(saved["bytes"])}))
	if not str(options["result"]).is_empty():
		var payload := {
			"schema": RESULT_SCHEMA,
			"story": _story_meta(),
			"state": _runtime.current_state(),
			"runtime": {
				"target_id": "GODOT_4_RUNTIME_PROJECT_V1",
				"engine": str(Engine.get_version_info().get("string", "")),
				"story_schema": str(_runtime.story.get("schema", "")),
				"save_schema": "poemseed-godot-save/1",
			},
		}
		var written: Dictionary = _save_store.write(str(options["result"]), payload)
		if not bool(written["ok"]):
			_emit_error("RESULT_WRITE_FAILED", str(written["error"]))
			return 3
		print("POEMSEED_RESULT " + JSON.stringify({"path": str(options["result"]),
			"sha256": str(written["sha256"]), "bytes": int(written["bytes"])}))
	var final_state: Dictionary = _runtime.current_state()
	print("POEMSEED_DONE " + JSON.stringify({"steps": final_state["steps"], "status": final_state["status"],
		"path": final_state["path"]}))
	return 0


func _story_meta() -> Dictionary:
	var story: Dictionary = _runtime.story
	return {
		"story_id": str(story.get("story_id", "")),
		"revision": int(story.get("revision", 0)),
		"title": str(story.get("title", "")),
		"spec_digest": str(story.get("spec_digest", "")),
		"source_digest": str(story.get("source_digest", "")),
		"review_receipt": str(story.get("review_receipt", "")),
		"format_version": str(story.get("format_version", "")),
		"schema": str(story.get("schema", "")),
	}


func _emit_state() -> void:
	print(STATE_PREFIX + JSON.stringify(_runtime.current_state()))


func _emit_error(code: String, detail: String) -> void:
	print("POEMSEED_ERROR " + JSON.stringify({"code": code, "detail": detail}))
