import json
import subprocess


class _Content:
    def __init__(self, text):
        self.text = text


class _Response:
    def __init__(self, text):
        self.content = [_Content(text)]


class _Messages:
    def create(self, *, model, max_tokens, messages, **kwargs):
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.insert(0, content)
            else:
                parts.append(content)
        prompt = "\n\n".join(parts)

        result = subprocess.run(
            ["claude", "--print", "--output-format", "json", "--model", model, prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude CLI error: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude CLI returned error: {data}")

        return _Response(data["result"])


class ClaudeClient:
    """Thin wrapper around the `claude` CLI for use without an API key."""

    def __init__(self):
        self.messages = _Messages()
