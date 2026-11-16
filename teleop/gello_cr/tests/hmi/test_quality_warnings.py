"""Published dataset quality warnings remain visible to the operator."""

import pytest

from teleop.gello_cr.tests.hmi.test_collection_controller import page, show  # noqa: F401


@pytest.mark.parametrize(
    ("report", "state", "required"),
    [
        (
            {"valid": True, "errors": [], "warnings": ["Episodes need review: [1, 3]"]},
            "warning",
            ("复核", "Episodes need review: [1, 3]"),
        ),
        ({"valid": True, "errors": [], "warnings": []}, "success", ("已完成并发布",)),
        (
            {"valid": False, "errors": ["坏帧"], "warnings": ["需要复核"]},
            "error",
            ("校验失败", "坏帧", "需要复核"),
        ),
    ],
)
def test_published_dataset_receipt_shows_validation_details(page, report, state, required):  # noqa: F811
    widget, _ = page
    show(widget, {"session_active": False, "root": "/data/final", "validation": report})
    assert not widget.save_receipt.isHidden()
    assert widget.save_receipt.property("state") == state
    for text in required:
        assert text in widget.save_receipt.text()
    for text in report["errors"] + report["warnings"]:
        assert text in widget.episode_status.text()
