"""Tests for the deterministic SAM 3.1 output parser (app.sam.parser).

Every input here is a hand-written string matching (or deliberately
violating) the documented grammar -- no network call, no real SAM
response, is ever used.
"""

from __future__ import annotations

import pytest

from app.sam.parser import SAMParseError, parse_sam_output

# --- A. one object with box + mask -----------------------------------------


def test_parses_one_object_with_box_and_mask():
    raw = "<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|><|mask;x=0;y=0;data=122,376,~abc|>"

    result = parse_sam_output(raw)

    assert len(result.segmentations) == 1
    seg = result.segmentations[0]
    assert seg.frame_index == 0
    assert seg.object_index == 0
    assert seg.bounding_box.x1 == 181
    assert seg.bounding_box.y1 == 365
    assert seg.bounding_box.x2 == 556
    assert seg.bounding_box.y2 == 486
    assert seg.bounding_box.width == 1516
    assert seg.bounding_box.height == 1600
    assert seg.bounding_box.confidence is None
    assert seg.mask is not None
    assert seg.mask.x == 0
    assert seg.mask.y == 0
    assert seg.mask.encoded_data == "122,376,~abc"
    assert seg.mask.encoding == "lossless"
    assert result.raw_output == raw


# --- B. multiple objects -----------------------------------------------


def test_parses_multiple_objects_in_one_frame():
    raw = (
        "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>,"
        "1<|box;x1=5;y1=6;x2=7;y2=8;w=10;h=10|><|mask;x=0;y=0;data=2,~b|>"
    )

    result = parse_sam_output(raw)

    assert len(result.segmentations) == 2
    assert [seg.object_index for seg in result.segmentations] == [0, 1]
    assert result.segmentations[1].bounding_box.x1 == 5


def test_parses_multiple_frames_as_separate_lines():
    raw = (
        "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>\n"
        "<1f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>"
    )

    result = parse_sam_output(raw)

    assert len(result.segmentations) == 2
    assert result.segmentations[0].frame_index == 0
    assert result.segmentations[1].frame_index == 1


# --- C. optional confidence present -----------------------------------------


def test_box_and_mask_confidence_preserved_when_present():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10;c=0.91|><|mask;x=0;y=0;c=0.5;data=1,~a|>"

    result = parse_sam_output(raw)

    seg = result.segmentations[0]
    assert seg.bounding_box.confidence == pytest.approx(0.91)
    assert seg.mask.confidence == pytest.approx(0.5)


# --- D. confidence absent -----------------------------------------


def test_confidence_absent_stays_none_not_fabricated():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>"

    result = parse_sam_output(raw)

    seg = result.segmentations[0]
    assert seg.bounding_box.confidence is None
    assert seg.mask.confidence is None


# --- E. malformed box token -----------------------------------------


def test_malformed_box_token_missing_field_raises():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>"  # missing y2

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


def test_malformed_box_token_non_numeric_field_raises():
    raw = "<0f>0<|box;x1=one;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>"

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


# --- F. malformed mask token -----------------------------------------


def test_malformed_mask_token_missing_data_field_raises():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0|>"  # missing data

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


def test_malformed_mask_token_non_numeric_field_raises():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=zero;y=0;data=1,~a|>"

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


# --- G. incomplete segmentation -----------------------------------------


def test_segmentation_with_mask_but_no_box_raises():
    raw = "<0f>0<|mask;x=0;y=0;data=1,~a|>"

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


def test_segmentation_with_box_but_no_mask_is_allowed_box_only():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"

    result = parse_sam_output(raw)

    assert len(result.segmentations) == 1
    assert result.segmentations[0].mask is None


def test_line_without_frame_marker_raises():
    raw = "0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"

    with pytest.raises(SAMParseError):
        parse_sam_output(raw)


# --- H. empty / no-detection output -----------------------------------------


def test_empty_output_yields_zero_segmentations_not_an_error():
    result = parse_sam_output("")

    assert result.segmentations == []
    assert result.raw_output == ""


def test_whitespace_only_output_yields_zero_segmentations():
    result = parse_sam_output("   \n  ")

    assert result.segmentations == []


def test_frame_marker_with_no_objects_yields_zero_segmentations():
    result = parse_sam_output("<0f>")

    assert result.segmentations == []


# --- one_bit encoding marker -----------------------------------------


def test_one_bit_mask_encoding_detected():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,!a|>"

    result = parse_sam_output(raw)

    assert result.segmentations[0].mask.encoding == "one_bit"


def test_unknown_mask_encoding_when_no_marker_present():
    raw = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,2,3|>"

    result = parse_sam_output(raw)

    assert result.segmentations[0].mask.encoding == "unknown"
