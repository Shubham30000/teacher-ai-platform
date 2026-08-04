"""Shared pytest fixtures. Sample DOCX/PPTX files are built at test time
(rather than checked in as binaries) so fixtures always match the
current python-docx/python-pptx versions in requirements.txt."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_txt_path(tmp_path: Path) -> Path:
    content = """Force and Pressure

Chapter 8

1. Introduction

Push or pull is called force. A force can change the shape, speed, or
direction of an object.

1.1 Types of Force

- Muscular force
- Gravitational force
- Frictional force

1.2 Pressure

Pressure is the force acting per unit area. It is calculated as
Pressure = Force / Area.

See https://ncert.nic.in/textbook.php for the full NCERT chapter.

SUMMARY

Force and pressure are related but distinct physical quantities.
"""
    path = tmp_path / "force_and_pressure.txt"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def sample_docx_path(tmp_path: Path) -> Path:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Force and Pressure", level=0)
    document.add_heading("1. Introduction", level=1)
    document.add_paragraph(
        "Push or pull is called force. A force can change the shape, speed, "
        "or direction of an object."
    )
    document.add_heading("1.1 Types of Force", level=2)
    document.add_paragraph("Muscular force", style="List Bullet")
    document.add_paragraph("Gravitational force", style="List Bullet")

    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Quantity"
    table.cell(0, 1).text = "Unit"
    table.cell(1, 0).text = "Force"
    table.cell(1, 1).text = "Newton"

    path = tmp_path / "force_and_pressure.docx"
    document.save(str(path))
    return path


@pytest.fixture
def sample_pptx_path(tmp_path: Path) -> Path:
    pptx_module = pytest.importorskip("pptx")

    presentation = pptx_module.Presentation()
    layout = presentation.slide_layouts[1]

    slide1 = presentation.slides.add_slide(layout)
    slide1.shapes.title.text = "Force and Pressure"
    body = slide1.placeholders[1].text_frame
    body.text = "Push or pull is called force."
    p = body.add_paragraph()
    p.text = "Pressure is force per unit area."
    p.level = 1

    slide2 = presentation.slides.add_slide(layout)
    slide2.shapes.title.text = "Types of Force"
    body2 = slide2.placeholders[1].text_frame
    body2.text = "Muscular force"

    path = tmp_path / "force_and_pressure.pptx"
    presentation.save(str(path))
    return path
