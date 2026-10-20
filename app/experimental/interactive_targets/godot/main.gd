extends Control
## PoemSeed Studio B07 fixed Godot 4 runtime entry point (target GODOT_4_RUNTIME_PROJECT_V1).
## Copied verbatim from app/experimental/interactive_targets/godot/main.gd by the exporter.
## It only interprets res://data/story.json through the fixed typed-AST runtime below.
## It never evaluates generated code, never loads remote resources and never opens
## arbitrary files: the only data read is res://data/story.json, and the only writes are
## user:// files named explicitly on the command line for controlled acceptance runs.
## Labels and Buttons are plain text, so BBCode/HTML is never parsed or executed.

const StoryLoader = preload("res://runtime/story_loader.gd")
const StoryRuntime = preload("res://runtime/story_runtime.gd")
const SaveStore = preload("res://runtime/save_store.gd")
const AcceptanceRunner = preload("res://runtime/acceptance_runner.gd")

const STORY_PATH := "res://data/story.json"

var _runtime = null
var _runtime_ready := false
var _ui_built := false

var _title_label: Label
var _speaker_label: Label
var _dialogue_label: Label
var _ending_label: Label
var _status_label: Label
var _choices_box: VBoxContainer


func _ready() -> void:
	var loaded: Dictionary = StoryLoader.load_file(STORY_PATH)
	if not bool(loaded["ok"]):
		_fail_soft("STORY_LOAD_FAILED", str(loaded["detail"]))
		return
	_runtime = StoryRuntime.new(loaded["story"])
	if not bool(_runtime.is_valid()):
		_fail_soft("RUNTIME_INVALID", str(_runtime.error_detail))
		return
	_runtime_ready = true
	var user_args: PackedStringArray = OS.get_cmdline_user_args()
	if AcceptanceRunner.wants_acceptance(user_args):
		var runner = AcceptanceRunner.new(_runtime, SaveStore)
		var code: int = runner.run(user_args)
		get_tree().quit(code)
		return
	if DisplayServer.get_name() == "headless":
		print("POEMSEED_ERROR " + JSON.stringify({
			"code": "HEADLESS_REQUIRES_ACCEPTANCE_ARGUMENTS",
			"detail": "headless runs must pass controlled acceptance arguments after --"}))
		get_tree().quit(3)
		return
	_build_ui()
	_render()


func _fail_soft(code: String, detail: String) -> void:
	print("POEMSEED_ERROR " + JSON.stringify({"code": code, "detail": detail}))
	if DisplayServer.get_name() == "headless":
		get_tree().quit(3)
		return
	_build_ui()
	_title_label.text = "PoemSeed interactive story"
	_speaker_label.text = ""
	_dialogue_label.text = "This story project cannot be loaded safely."
	_ending_label.text = code
	_status_label.text = "FAILED: " + detail
	_choices_box.add_child(_make_label("No choices are available."))


func _build_ui() -> void:
	if _ui_built:
		return
	_ui_built = true
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_top", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_bottom", 24)
	add_child(margin)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	margin.add_child(box)
	_title_label = _make_label("")
	_title_label.add_theme_font_size_override("font_size", 22)
	box.add_child(_title_label)
	_speaker_label = _make_label("")
	_speaker_label.add_theme_font_size_override("font_size", 18)
	box.add_child(_speaker_label)
	_dialogue_label = _make_label("")
	_dialogue_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_dialogue_label.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	box.add_child(_dialogue_label)
	_ending_label = _make_label("")
	box.add_child(_ending_label)
	_choices_box = VBoxContainer.new()
	_choices_box.add_theme_constant_override("separation", 8)
	box.add_child(_choices_box)
	_status_label = _make_label("")
	_status_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
	box.add_child(_status_label)


func _make_label(text_value: String) -> Label:
	var label := Label.new()
	label.text = text_value
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func _render() -> void:
	if not _runtime_ready or not _ui_built:
		return
	var story: Dictionary = _runtime.story
	var state: Dictionary = _runtime.current_state()
	var node: Dictionary = state["node"]
	_title_label.text = str(story["title"]) + " - " + str(node["title"])
	_speaker_label.text = str(node["speaker"])
	_dialogue_label.text = str(node["dialogue"])
	_ending_label.text = str(node["ending"])
	for child in _choices_box.get_children():
		child.queue_free()
	for choice in state["choices"]:
		var button := Button.new()
		button.text = str(choice["label"])
		button.disabled = not bool(choice["enabled"])
		button.pressed.connect(_on_choice_pressed.bind(str(choice["id"])))
		_choices_box.add_child(button)
	var status := str(state["status"])
	var progress := "Steps " + str(state["steps"]) + " / " + str(state["max_steps"])
	if status == "STEP_CAP_REACHED":
		progress = "Step cap reached (" + str(state["max_steps"]) + "). " + progress
	elif status == "NO_EXIT":
		progress = "No available choice at this node."
	_status_label.text = status + " - " + progress


func _on_choice_pressed(choice_id: String) -> void:
	if not _runtime_ready:
		return
	var result: Dictionary = _runtime.advance(choice_id)
	if not bool(result["ok"]):
		_status_label.text = "CHOICE_REJECTED: " + str(result["error"])
		return
	_render()
