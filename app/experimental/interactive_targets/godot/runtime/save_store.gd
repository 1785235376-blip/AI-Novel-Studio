extends RefCounted
## PoemSeed Studio B07 fixed save/restore store (target GODOT_4_RUNTIME_PROJECT_V1).
## Save files are local JSON only, limited to an explicit user:// path with plain ASCII
## path segments ending in .json, bounded to 64 KiB. Reads are validated structurally;
## story identity and replay consistency are checked by the interpreter before use.

const SAVE_SCHEMA := "poemseed-godot-save/1"
const SAVE_SCHEMA_VERSION := 1
const RESULT_SCHEMA := "poemseed-godot-runtime-result/1"
const MAX_JSON_BYTES := 65536
const MAX_PATH_LENGTH := 160


static func is_allowed_user_path(value) -> bool:
	if typeof(value) != TYPE_STRING:
		return false
	var path := str(value)
	if path.length() > MAX_PATH_LENGTH:
		return false
	if not path.begins_with("user://"):
		return false
	var relative := path.substr(7)
	if relative.is_empty() or relative.length() > MAX_PATH_LENGTH - 7:
		return false
	if relative.begins_with("/") or relative.contains("\\") or relative.contains(":"):
		return false
	if relative.contains(".."):
		return false
	var segments := relative.split("/")
	for segment in segments:
		if not _safe_segment(segment):
			return false
	if not relative.to_lower().ends_with(".json"):
		return false
	return true


static func write(path, payload: Dictionary) -> Dictionary:
	if not is_allowed_user_path(path):
		return {"ok": false, "error": "USER_PATH_INVALID"}
	var text := JSON.stringify(payload, "  ", true)
	var data := text.to_utf8_buffer()
	if data.size() > MAX_JSON_BYTES:
		return {"ok": false, "error": "JSON_TOO_LARGE"}
	var file := FileAccess.open(str(path), FileAccess.WRITE)
	if file == null:
		return {"ok": false, "error": "FILE_WRITE_FAILED"}
	file.store_buffer(data)
	file.close()
	return {"ok": true, "error": "", "bytes": data.size(), "sha256": text.sha256_text()}


static func read(path) -> Dictionary:
	if not is_allowed_user_path(path):
		return {"ok": false, "error": "USER_PATH_INVALID", "save": {}}
	var text_path := str(path)
	if not FileAccess.file_exists(text_path):
		return {"ok": false, "error": "FILE_NOT_FOUND", "save": {}}
	var file := FileAccess.open(text_path, FileAccess.READ)
	if file == null:
		return {"ok": false, "error": "FILE_READ_FAILED", "save": {}}
	var size := file.get_length()
	if size <= 0 or size > MAX_JSON_BYTES:
		file.close()
		return {"ok": false, "error": "FILE_SIZE_INVALID", "save": {}}
	var text := file.get_as_text()
	file.close()
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"ok": false, "error": "JSON_INVALID", "save": {}}
	var save: Dictionary = parsed
	if str(save.get("schema", "")) != SAVE_SCHEMA:
		return {"ok": false, "error": "SAVE_SCHEMA_INVALID", "save": {}}
	var schema_version = save.get("save_schema_version", null)
	if not _is_integer(schema_version) or _to_int(schema_version) != SAVE_SCHEMA_VERSION:
		return {"ok": false, "error": "SAVE_SCHEMA_VERSION_INVALID", "save": {}}
	var identity = save.get("story", null)
	if typeof(identity) != TYPE_DICTIONARY:
		return {"ok": false, "error": "SAVE_STORY_INVALID", "save": {}}
	for key in ["id", "spec_digest", "source_digest", "review_receipt"]:
		if typeof(identity.get(key, null)) != TYPE_STRING or str(identity.get(key, "")).is_empty():
			return {"ok": false, "error": "SAVE_STORY_INVALID", "save": {}}
	var revision = identity.get("revision", null)
	if not _is_integer(revision) or _to_int(revision) < 1:
		return {"ok": false, "error": "SAVE_STORY_INVALID", "save": {}}
	if typeof(save.get("current_node_id", null)) != TYPE_STRING:
		return {"ok": false, "error": "SAVE_STATE_INVALID", "save": {}}
	if typeof(save.get("path", null)) != TYPE_ARRAY:
		return {"ok": false, "error": "SAVE_STATE_INVALID", "save": {}}
	if typeof(save.get("variables", null)) != TYPE_DICTIONARY:
		return {"ok": false, "error": "SAVE_STATE_INVALID", "save": {}}
	var steps = save.get("steps", null)
	if not _is_integer(steps) or _to_int(steps) < 0:
		return {"ok": false, "error": "SAVE_STATE_INVALID", "save": {}}
	return {"ok": true, "error": "", "save": save}


static func _safe_segment(segment: String) -> bool:
	if segment.is_empty() or segment.length() > 64:
		return false
	if segment == "." or segment == "..":
		return false
	if segment.ends_with(".") or segment.ends_with(" "):
		return false
	var first := segment.unicode_at(0)
	if not _is_alnum(first):
		return false
	for index in range(segment.length()):
		var code := segment.unicode_at(index)
		if not _is_alnum(code) and code != 46 and code != 95 and code != 45:
			return false
	return true


static func _is_alnum(code: int) -> bool:
	var upper := code >= 65 and code <= 90
	var lower := code >= 97 and code <= 122
	var digit := code >= 48 and code <= 57
	return upper or lower or digit


static func _is_integer(value) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	if typeof(value) == TYPE_FLOAT:
		var number := float(value)
		return is_finite(number) and number == floor(number)
	return false


static func _to_int(value) -> int:
	if typeof(value) == TYPE_INT:
		return int(value)
	return int(float(value))
