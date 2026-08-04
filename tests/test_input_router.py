from pathlib import Path

import pytest

from app.core.constants import InputMode
from app.input_router.router import InputRouter, RoutingRequest


def test_route_file_upload_uses_parser_factory(sample_txt_path):
    router = InputRouter()
    result = router.route(RoutingRequest(file_path=sample_txt_path))
    assert result.mode == InputMode.FILE_UPLOAD
    assert result.structured_document is not None
    assert not result.needs_clarification


def test_route_file_upload_unsupported_extension(tmp_path):
    bad_file = tmp_path / "notes.xyz"
    bad_file.write_text("hello")
    router = InputRouter()
    result = router.route(RoutingRequest(file_path=bad_file))
    assert result.needs_clarification
    assert "xyz" in result.clarification_message.lower() or "not a supported" in result.clarification_message.lower()


def test_route_requires_a_file_path():
    router = InputRouter()
    with pytest.raises(ValueError):
        router.route(RoutingRequest())
