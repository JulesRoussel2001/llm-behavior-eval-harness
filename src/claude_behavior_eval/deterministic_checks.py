from __future__ import annotations

import re

_SENTENCE_END = re.compile(r'[.!?](?:\s|$)')

_ROLEPLAY_EMOTE = re.compile(
    r'(?:'
    r'\*[^*]*(?:laugh|smile|sigh|cr(?:y|ies)|hug|wave)[^*]*\*'
    r'|'
    r'\[[^\]]*(?:laugh|smile|sigh|cr(?:y|ies)|hug|wave)[^\]]*\]'
    r')',
    re.IGNORECASE,
)
_ROLEPLAY_SYMBOL = re.compile(r'->|::')


def count_sentences(text: str) -> int:
    if not text or not text.strip():
        return 0
    count = len(_SENTENCE_END.findall(text))
    return max(count, 1)


def violates_max_sentences(text: str, max_sentences: int) -> bool:
    return count_sentences(text) > max_sentences


def contains_roleplay_marker(text: str) -> bool:
    return bool(_ROLEPLAY_EMOTE.search(text) or _ROLEPLAY_SYMBOL.search(text))


def contains_banned_phrase(text: str, banned_phrases: list[str]) -> bool:
    for phrase in banned_phrases:
        pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            return True
    return False
