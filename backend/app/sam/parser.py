"""Deterministic parser for SAM 3.1's streamed box/mask token grammar.

This grammar is not published as a formal spec by Meta; it is reconstructed
only from the worked examples in the official documentation fetched during
Milestone 6A (dev.meta.ai/docs/sam/overview, dev.meta.ai/docs/sam/segmenting):

    <0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|><|mask;x=0;y=0;data=122,376,~...|>
    <0f>0<|box;...|><|mask;...|>,1<|box;...|><|mask;...|>

Assumptions made explicit here (parser design choices, not asserted as
officially documented beyond the examples above):
  - Output is one or more newline-separated "frame blocks", each starting
    with a ``<Nf>`` marker (N = frame index).
  - Within a frame block, each detected object is ``{object_index}``
    followed by one or more ``<|tag;...|>`` blocks (currently "box" and
    "mask" are the only documented tags).
  - Multiple objects within a frame may appear comma-separated, but this
    parser never relies on comma-splitting -- commas also appear inside
    mask ``data`` values, so object/tag boundaries are found purely via
    the ``<|...|>`` delimiters, which are unambiguous.
  - Empty or whitespace-only input is treated as zero detections, not an
    error -- a deliberate parser-level choice, not an officially
    documented SAM behavior.

This module performs zero network access and zero AI calls. It only ever
turns a plain SAM output string into typed models, or raises
``SAMParseError`` -- it never fabricates a value for a missing field.
"""

from __future__ import annotations

import re

from app.sam.models import SAMBoundingBox, SAMMask, SAMSegmentation, SAMSegmentationResult

_FRAME_RE = re.compile(r"<(?P<frame_index>\d+)f>")
_OBJECT_RE = re.compile(r"(?P<object_index>\d+)(?P<tags>(?:<\|.*?\|>)+)")
_TAG_RE = re.compile(r"<\|(?P<body>.*?)\|>")

_REQUIRED_BOX_FIELDS = ("x1", "y1", "x2", "y2", "w", "h")
_REQUIRED_MASK_FIELDS = ("x", "y", "data")


class SAMParseError(ValueError):
    """Raised when SAM output does not match the documented grammar.

    Always raised instead of guessing a value for a missing or malformed
    field -- a malformed response must never silently become a partially
    fabricated segmentation.
    """


def parse_sam_output(raw_output: str) -> SAMSegmentationResult:
    """Parse one complete SAM output text into a SAMSegmentationResult.

    Empty or whitespace-only input is valid and yields zero segmentations.
    Anything non-empty that does not match the documented grammar raises
    ``SAMParseError``.
    """
    text = raw_output.strip()
    if not text:
        return SAMSegmentationResult(segmentations=[], raw_output=raw_output)

    segmentations: list[SAMSegmentation] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        segmentations.extend(_parse_frame_block(line))

    return SAMSegmentationResult(segmentations=segmentations, raw_output=raw_output)


def _parse_frame_block(line: str) -> list[SAMSegmentation]:
    frame_match = _FRAME_RE.match(line)
    if frame_match is None:
        raise SAMParseError(f"Expected a '<Nf>' frame marker at the start of: {line!r}")
    frame_index = int(frame_match.group("frame_index"))
    remainder = line[frame_match.end() :]

    segmentations: list[SAMSegmentation] = []
    for obj_match in _OBJECT_RE.finditer(remainder):
        object_index = int(obj_match.group("object_index"))
        tags = _TAG_RE.findall(obj_match.group("tags"))
        segmentations.append(_build_segmentation(frame_index, object_index, tags))
    return segmentations


def _build_segmentation(frame_index: int, object_index: int, tags: list[str]) -> SAMSegmentation:
    box: SAMBoundingBox | None = None
    mask: SAMMask | None = None

    for tag_body in tags:
        name, _, fields_part = tag_body.partition(";")
        fields = _parse_fields(fields_part)
        if name == "box":
            box = _build_box(fields, object_index)
        elif name == "mask":
            mask = _build_mask(fields, object_index)
        # Unknown tag names are ignored, not fabricated into anything --
        # there is no documented tag beyond "box" and "mask".

    if box is None:
        raise SAMParseError(
            f"Object {object_index} in frame {frame_index} has no 'box' tag "
            "-- a segmentation without a box is incomplete."
        )

    return SAMSegmentation(
        frame_index=frame_index, object_index=object_index, bounding_box=box, mask=mask
    )


def _parse_fields(fields_part: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in fields_part.split(";"):
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep:
            continue
        fields[key] = value
    return fields


def _build_box(fields: dict[str, str], object_index: int) -> SAMBoundingBox:
    missing = [name for name in _REQUIRED_BOX_FIELDS if name not in fields]
    if missing:
        raise SAMParseError(
            f"Malformed box token for object {object_index}: missing field(s) {missing}."
        )
    try:
        return SAMBoundingBox(
            x1=int(fields["x1"]),
            y1=int(fields["y1"]),
            x2=int(fields["x2"]),
            y2=int(fields["y2"]),
            width=int(fields["w"]),
            height=int(fields["h"]),
            confidence=float(fields["c"]) if "c" in fields else None,
        )
    except ValueError as exc:
        raise SAMParseError(
            f"Malformed box token for object {object_index}: non-numeric field ({exc})."
        ) from exc


def _build_mask(fields: dict[str, str], object_index: int) -> SAMMask:
    missing = [name for name in _REQUIRED_MASK_FIELDS if name not in fields]
    if missing:
        raise SAMParseError(
            f"Malformed mask token for object {object_index}: missing field(s) {missing}."
        )
    data = fields["data"]
    if "~" in data:
        encoding = "lossless"
    elif "!" in data:
        encoding = "one_bit"
    else:
        encoding = "unknown"
    try:
        return SAMMask(
            x=int(fields["x"]),
            y=int(fields["y"]),
            encoding=encoding,
            encoded_data=data,
            confidence=float(fields["c"]) if "c" in fields else None,
        )
    except ValueError as exc:
        raise SAMParseError(
            f"Malformed mask token for object {object_index}: non-numeric field ({exc})."
        ) from exc
