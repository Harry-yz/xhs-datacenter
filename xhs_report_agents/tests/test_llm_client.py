from __future__ import annotations

import pytest

from xhs_report_agents.llm_client import LLMError, _loads_json_object


def test_loads_json_object_plain():
    assert _loads_json_object('{"ok": true}') == {"ok": True}


def test_loads_json_object_fenced():
    assert _loads_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_loads_json_object_rejects_array():
    with pytest.raises(LLMError):
        _loads_json_object("[1,2,3]")

