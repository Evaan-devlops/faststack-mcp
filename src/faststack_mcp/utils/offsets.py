from __future__ import annotations


def build_line_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for line in text.splitlines(True):
        total += len(line.encode("utf-8"))
        offsets.append(total)
    return offsets


def line_to_byte(offsets: list[int], line_no: int, col: int = 0) -> int:
    if not offsets:
        return 0
    idx = max(0, line_no - 1)
    if idx >= len(offsets):
        return offsets[-1]
    return offsets[idx] + col


def line_span_to_bytes(
    offsets: list[int],
    start_line: int,
    end_line: int,
    start_col: int = 0,
    end_col: int = 0,
) -> tuple[int, int]:
    start = line_to_byte(offsets, start_line, start_col)
    if end_line <= 0:
        end = start
    else:
        end = line_to_byte(offsets, end_line, end_col)
        if end <= start:
            if end_line < len(offsets):
                end = offsets[end_line]
            elif offsets:
                end = offsets[-1]
    return start, end
