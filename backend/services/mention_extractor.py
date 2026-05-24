"""Extract @mentions from comment bodies.

Mention rule: ``@<username>`` where username is 3-30 chars of
``[A-Za-z0-9_]``, not surrounded by other identifier chars. Mentions inside
backtick-delimited code spans are ignored.
"""

import re

_MENTION_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{3,30})(?![A-Za-z0-9_])")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def extract_mention_usernames(body: str) -> list[str]:
    """Return unique mention usernames in first-appearance order.

    Code spans (anything between matching backticks on the same line) are
    stripped before matching, so ``@user`` inside `` `like @this` `` does not
    count.
    """
    if not body:
        return []
    stripped = _CODE_SPAN_RE.sub("", body)
    seen: list[str] = []
    for match in _MENTION_RE.finditer(stripped):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen
