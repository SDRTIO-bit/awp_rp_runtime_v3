from types import SimpleNamespace

from awp_rp_runtime_v3.adapters.llm.deepseek_adapter import DeepSeekAdapter


class _StreamingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return iter([
                SimpleNamespace(choices=[SimpleNamespace(
                    delta=SimpleNamespace(content=None, reasoning_content="planning"),
                )]),
            ])
        return iter([
            SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content="正文"),
            )]),
        ])


def test_streaming_writer_retries_when_thinking_consumes_all_output_tokens() -> None:
    completions = _StreamingCompletions()
    adapter = DeepSeekAdapter(default_max_tokens=4000)
    adapter._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    received: list[str] = []

    result = adapter._call_openai_text_stream(
        "prompt", 4000, "model", {"thinking": {"type": "enabled"}}, None,
        received.append,
    )

    assert result == "正文"
    assert received == ["正文"]
    assert completions.calls[1]["max_tokens"] == 16000
