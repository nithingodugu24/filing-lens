"""Readable provisional text from streamed answer JSON. Final validation remains mandatory."""

import json
import re
import time


class StreamCancelled(Exception):
    pass


def check_cancelled(cancelled):
    if cancelled and cancelled():
        raise StreamCancelled()


def string_prefix(raw, start):
    index = start
    while index < len(raw):
        if raw[index] == '"':
            return json.loads('"' + raw[start:index] + '"')
        if raw[index] == "\\":
            size = 6 if index + 1 < len(raw) and raw[index + 1] == "u" else 2
            if index + size > len(raw):
                break
            index += size
        else:
            index += 1
    return json.loads('"' + raw[start:index] + '"')


class AnswerProgress:
    def __init__(self, emit, cancelled=None):
        self.emit, self.cancelled = emit, cancelled
        self.raw, self.preview, self.last_sent = "", "", 0

    def feed(self, delta, force=False):
        check_cancelled(self.cancelled)
        self.raw += delta
        if len(self.raw) > 131072:
            from .providers import ProviderError

            raise ProviderError("The streamed response exceeded the answer size limit.")
        if not force and self.preview and time.monotonic() - self.last_sent < 0.03:
            return
        try:
            text = "\n\n".join(
                string_prefix(self.raw, m.end()) for m in re.finditer(r'"text"\s*:\s*"', self.raw)
            )
        except (ValueError, json.JSONDecodeError):
            return
        if text and text != self.preview:
            if text.startswith(self.preview):
                self.emit("delta", {"text": text[len(self.preview) :]})
            else:
                self.emit("draft", {"text": text})
            self.preview, self.last_sent = text, time.monotonic()
