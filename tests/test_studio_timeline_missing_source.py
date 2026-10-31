"""A missing actual source file must not start a timeline render."""
from test_studio_canvas_video_bridge import bridge, render_calls, queue, execute, get
from test_studio_canvas_audio_return import rig


def test_missing_video_bytes_blocks_queued_timeline(bridge, render_calls):
    e = bridge
    queued = queue(e)
    source_file = e.assets._bin_path(e.source["id"])
    assert source_file.resolve().is_relative_to(e.root.resolve())
    assert source_file.is_file()
    source_file.unlink()
    outcome = execute(e, queued)
    current = get(e, queued)
    assert outcome["status"] == "UNKNOWN" and outcome["output_candidate"] is None
    assert outcome["error_code"] == "STUDIO_TIMELINE_OUTCOME_UNKNOWN"
    assert outcome["automatic_replay"] is False
    assert current["status"] == outcome["status"] and current["output_candidate"] is None
    assert render_calls == []
