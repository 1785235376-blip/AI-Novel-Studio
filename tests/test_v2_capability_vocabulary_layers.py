"""The three capability vocabularies must never be conflated.

Phase10 found that two mappings in circulation were imprecise, so this pins the
real structure rather than restating it in prose:

* **model capability** — `app/model_center/domain.py::Capability`, ten values.
  FLUX is `IMAGE` here.
* **task capability** — `app/model_provider_contracts.py::TaskType`. This is a
  *different* vocabulary: `IMAGE_GENERATION`, not `IMAGE`.
* **graph node binding** — node-local names such as `ASR`. `ASR` is **not** a
  model capability and **not** a runtime type; it is the binding Whisper's
  execution node declares.

The mapping is one-directional: a task name resolves *down* to a model capability
through `TASK_CAPABILITY`, and nothing resolves a model capability up to a task.
"""
from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from app.model_center.domain import Capability, RuntimeType

MODEL_CAPABILITIES = {item.value for item in Capability}
RUNTIME_TYPES = {item.value for item in RuntimeType}


def _task_vocabulary() -> tuple[frozenset[str], dict[str, str]]:
    from app.model_provider_contracts import TASK_CAPABILITY, TaskType

    declared = frozenset(get_args(TaskType))
    return declared, dict(TASK_CAPABILITY)


def test_task_vocabulary_is_disjoint_from_the_model_vocabulary():
    """No task name may masquerade as a model capability (IMAGE_GENERATION != IMAGE)."""
    declared, _ = _task_vocabulary()
    assert declared, "the task vocabulary must not be empty"
    assert declared & MODEL_CAPABILITIES == set()
    assert "IMAGE_GENERATION" in declared and "IMAGE_GENERATION" not in MODEL_CAPABILITIES
    assert "IMAGE" in MODEL_CAPABILITIES and "IMAGE" not in declared


def test_every_task_type_maps_onto_a_real_model_capability():
    """The sanctioned crossing must be total and must land on real capabilities."""
    declared, mapping = _task_vocabulary()
    assert set(mapping) == set(declared), "every task type needs a declared mapping"
    assert set(mapping.values()) <= MODEL_CAPABILITIES
    assert mapping["IMAGE_GENERATION"] == "IMAGE"
    assert mapping["TEXT_GENERATION"] == "TEXT"
    assert mapping["VIDEO_GENERATION"] == "VIDEO"


def test_the_mapping_is_not_reversible_into_the_task_vocabulary():
    """`TEXT` must not uniquely pick a task: the crossing is one-directional."""
    _, mapping = _task_vocabulary()
    # Several model capabilities are simply not task types at all.
    assert {"AUDIO", "VISION", "TTS", "EMBEDDING", "RERANK", "RESTORATION",
            "INTERPOLATION"} <= MODEL_CAPABILITIES
    assert not ({"AUDIO", "VISION", "TTS"} & set(mapping.values()))


def test_asr_belongs_to_no_capability_or_runtime_vocabulary():
    """`ASR` is a graph node binding only - not a capability, not a runtime type."""
    assert "ASR" not in MODEL_CAPABILITIES
    assert "ASR" not in RUNTIME_TYPES
    _, mapping = _task_vocabulary()
    assert "ASR" not in mapping


def test_whisper_is_a_runtime_type_carrying_the_audio_capability():
    """Whisper: runtime `WHISPER_CPP`, model capability `AUDIO`, binding `ASR`."""
    assert "WHISPER_CPP" in RUNTIME_TYPES
    assert "AUDIO" in MODEL_CAPABILITIES

    source = Path(__file__).resolve().parents[1] / "app" / "model_center" / "whisper_runtime.py"
    text = source.read_text(encoding="utf-8")
    # The model definition carries AUDIO, and ASR appears only as a node binding.
    assert "(Capability.AUDIO,)" in text
    assert 'self.node.binding(self.provider_id, self.model_id, "ASR")' in text


def test_domain_never_declares_asr_as_a_capability_or_runtime():
    domain = Path(__file__).resolve().parents[1] / "app" / "model_center" / "domain.py"
    text = domain.read_text(encoding="utf-8")
    assert "ASR" not in text


def test_flux_is_registered_with_the_image_capability():
    """FLUX lives at the model-capability layer as IMAGE, under the COMFYUI runtime."""
    service = Path(__file__).resolve().parents[1] / "app" / "model_center" / "service.py"
    text = service.read_text(encoding="utf-8")
    assert '(Capability.IMAGE,),RuntimeType.COMFYUI' in text
    assert 'ModelDefinition("flux2-dev"' in text


@pytest.mark.parametrize("name", ["LOCAL_OLLAMA", "LM_STUDIO", "COMFYUI", "LLAMA_CPP", "API"])
def test_provider_families_are_a_fourth_vocabulary_and_never_a_capability(name):
    """Provider families name deployments; none of them is a model capability."""
    from app.model_provider_contracts import ProviderFamily

    assert name in set(get_args(ProviderFamily))
    assert name not in MODEL_CAPABILITIES


def test_provider_family_and_runtime_type_overlap_is_exactly_two_spellings():
    """A recorded conflation hazard, not an assumption.

    `ProviderFamily` and `RuntimeType` are different vocabularies, yet they share
    exactly two spellings — `COMFYUI` and `LLAMA_CPP`. This test asserts the
    overlap is *exactly* those two, so a new shared name is a deliberate decision
    rather than an accident. (`LM_STUDIO` deliberately has no runtime type: it is
    reached as `OPENAI_COMPATIBLE_LOCAL`.)
    """
    from app.model_provider_contracts import ProviderFamily

    families = set(get_args(ProviderFamily))
    assert families & RUNTIME_TYPES == {"COMFYUI", "LLAMA_CPP"}
    assert families - RUNTIME_TYPES == {"LOCAL_OLLAMA", "LM_STUDIO", "API"}
    assert "LM_STUDIO" not in RUNTIME_TYPES
