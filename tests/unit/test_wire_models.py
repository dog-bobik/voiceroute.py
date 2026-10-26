import json
import subprocess
import sys
from pathlib import Path

from voiceroute.models import UNSET, OpenEnumValue, WireObject, camel_to_snake, is_set


def test_wire_primitives_preserve_unknown_and_omitted_values() -> None:
    parsed = WireObject.parse({"id": "1", "futureField": 42}, frozenset({"id"}))

    assert parsed.values == {"id": "1"}
    assert parsed.additional_properties == {"futureField": 42}
    assert parsed.to_dict() == {"futureField": 42, "id": "1"}
    assert not is_set(UNSET)
    assert is_set(None)


def test_open_enum_and_naming_are_forward_compatible() -> None:
    known = OpenEnumValue.parse("ONLINE", frozenset({"ONLINE"}))
    future = OpenEnumValue.parse("STREAMING", frozenset({"ONLINE"}))

    assert known.known
    assert not future.known
    assert str(future) == "STREAMING"
    assert camel_to_snake("resumeGatewayUrl") == "resume_gateway_url"


def test_generator_is_deterministic_and_keeps_open_enums(tmp_path: Path) -> None:
    specification = {
        "openapi": "3.1.0",
        "components": {
            "schemas": {
                "GatewaySession": {
                    "type": "object",
                    "required": ["sequence"],
                    "properties": {
                        "sequence": {"type": "string"},
                        "status": {"type": "string", "enum": ["ONLINE", "IDLE"]},
                    },
                }
            }
        },
    }
    source = tmp_path / "openapi.json"
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    source.write_text(json.dumps(specification), encoding="utf-8")
    script = Path(__file__).parents[2] / "scripts" / "generate_wire_models.py"

    for target in (first, second):
        subprocess.run(
            [sys.executable, str(script), str(source), "--output", str(target)],
            check=True,
        )

    assert first.read_bytes() == second.read_bytes()
    generated = first.read_text(encoding="utf-8")
    assert "sequence: str" in generated
    assert "status: NotRequired[Literal['ONLINE', 'IDLE'] | str]" in generated
    subprocess.run(
        [
            sys.executable,
            str(script),
            str(source),
            "--output",
            str(first),
            "--check",
        ],
        check=True,
    )
