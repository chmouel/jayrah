import json
from typing import Any, IO

def safe_load(stream: IO[str] | str | bytes | None) -> Any:
    if stream is None:
        return None
    if hasattr(stream, 'read'):
        content = stream.read()
    else:
        content = stream
    if isinstance(content, bytes):
        content = content.decode()
    if not content:
        return None
    return json.loads(content)

def dump(data: Any, stream: IO[str] | None = None) -> str | None:
    text = json.dumps(data, indent=2)
    if stream is not None:
        stream.write(text)
        return None
    return text

def safe_dump(data: Any, stream: IO[str] | None = None, **kwargs) -> str | None:
    return dump(data, stream)
