#!/usr/bin/env python3
"""
Utilities for working with iMessage data
"""

import plistlib
from typing import Optional


def decode_attributed_body(blob: Optional[bytes]) -> Optional[str]:
    """
    Decode attributedBody blob to extract plain text from iMessage.

    iMessage stores formatted messages and attachments as binary plist data.
    This function attempts to extract readable text content.

    Args:
        blob: Binary data from message.attributedBody column

    Returns:
        Decoded text string, or None if unable to decode
    """
    if not blob:
        return None

    if isinstance(blob, memoryview):
        blob = blob.tobytes()

    # Try to parse as binary plist (NSKeyedArchiver)
    try:
        plist = plistlib.loads(blob)
        if isinstance(plist, dict):
            objects = plist.get('$objects') or []
            for obj in objects:
                if isinstance(obj, str) and obj:
                    return obj
            # Fallback: search other dict values
            for value in plist.values():
                if isinstance(value, str) and value:
                    return value
    except Exception:
        pass

    # Fallback: decode as UTF-8 and return the most word-rich chunk
    try:
        decoded = blob.decode('utf-8', errors='ignore')
        segments = []
        current = []
        for ch in decoded:
            if ch.isprintable() and ch not in {'\r', '\n', '\t'}:
                current.append(ch)
            else:
                if current:
                    segments.append(''.join(current))
                    current = []
        if current:
            segments.append(''.join(current))

        ignore_prefixes = (
            'NS', '__kIM', 'NSMutable', 'NSNumber', 'NSDictionary',
            'NSData', 'NSKeyed', 'streamtyped', 'DDScannerResult', 'NSArray',
            '"__kIMFileTransferGUID'
        )

        def score(segment: str) -> int:
            return sum(1 for c in segment if c.isalnum() or '\u4e00' <= c <= '\u9fff')

        cleaned = []
        for seg in segments:
            seg = seg.strip()
            if seg.startswith('+'):
                seg = seg.lstrip('+').strip()
            if not seg:
                continue
            if any(seg.startswith(prefix) for prefix in ignore_prefixes):
                continue
            if any(token in seg for token in ('classname', 'NSValue', 'NS.objects', 'NS.rangeval')):
                continue
            if seg and seg[0].isascii() and seg[0].isalpha() and len(seg) > 1 and '\u4e00' <= seg[1] <= '\u9fff':
                seg = seg[1:].lstrip()
            if seg == '￼':
                seg = '[Attachment]'
            cleaned.append(seg)

        preferred = [seg for seg in cleaned if any('\u4e00' <= c <= '\u9fff' for c in seg)]
        if preferred:
            cleaned = preferred
        if cleaned:
            best_match = max(cleaned, key=lambda seg: (score(seg), len(seg)))
            # Clean up leading single ASCII characters that are likely noise
            if best_match and len(best_match) > 1 and best_match[0].isascii() and not best_match[0].isalnum():
                best_match = best_match[1:].lstrip()
            return best_match
    except Exception:
        pass

    return None
