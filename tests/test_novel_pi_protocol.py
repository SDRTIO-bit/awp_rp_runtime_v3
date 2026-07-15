import pytest

from awp_rp_runtime_v3.contracts.novel_pi_protocol import (
    NovelPiFrame,
    NovelPiProtocolError,
    decode_frame,
    encode_frame,
)


def test_protocol_round_trip_preserves_request_id_and_payload():
    frame = NovelPiFrame(
        kind="tool_call",
        request_id="turn-1",
        payload={"name": "project_status"},
    )

    assert decode_frame(encode_frame(frame)) == frame


def test_protocol_rejects_unknown_frame_kind():
    with pytest.raises(NovelPiProtocolError, match="unsupported frame kind"):
        decode_frame(
            '{"schema_version":1,"kind":"shell","request_id":"x","payload":{}}'
        )


@pytest.mark.parametrize(
    "kind",
    ["role_init", "role_prompt", "role_end", "close_session"],
)
def test_protocol_accepts_role_host_frames(kind):
    frame = NovelPiFrame(kind=kind, request_id="role-1", payload={})

    assert decode_frame(encode_frame(frame)) == frame
