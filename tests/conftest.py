from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from closed_review.routes import CREDENTIAL_ENV


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "data"
    hermes = tmp_path / "hermes"
    monkeypatch.setenv("CREVIEW_HOME", str(store))
    monkeypatch.setenv("HERMES_HOME", str(hermes))
    monkeypatch.setenv("CREVIEW_TRUSTED_MODEL_URL", "http://127.0.0.1:8091/v1")
    monkeypatch.setenv("CREVIEW_MODEL", "qwen3.8-flash-next")
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_PROFILE", raising=False)
    monkeypatch.delenv("CREVIEW_TRUSTED_MODELS", raising=False)
    # Credentials and auxiliary overrides on the developer's machine must not leak into tests.
    for name in list(os.environ):
        if name in CREDENTIAL_ENV or name.startswith("AUXILIARY_") or name == "OPENAI_BASE_URL":
            monkeypatch.delenv(name, raising=False)
    return tmp_path


def write_docx(
    path: Path, paragraphs: list[tuple[str | None, str]], table: list[list[str]] | None = None
) -> None:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body: list[str] = []
    for style, text in paragraphs:
        props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        body.append(f"<w:p>{props}<w:r><w:t>{text}</w:t></w:r></w:p>")
    if table:
        rows = []
        for row in table:
            cells = "".join(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in row)
            rows.append(f"<w:tr>{cells}</w:tr>")
        body.append(f"<w:tbl>{''.join(rows)}</w:tbl>")
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{ns}"><w:body>{"".join(body)}'
        "<w:sectPr/></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", xml)


def write_pdf(path: Path, text: str = "Confidential review fixture") -> None:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode())
        payload.extend(obj)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)


def write_xlsx(path: Path) -> None:
    workbook_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relation_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_relation_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    workbook = (
        f'<workbook xmlns="{workbook_ns}" xmlns:r="{relation_ns}">'
        '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        f'<Relationships xmlns="{package_relation_ns}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    worksheet = (
        f'<worksheet xmlns="{workbook_ns}"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Group</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>n</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>A</t></is></c>'
        '<c r="B2"><v>21</v></c><c r="C2"><f>B2*2</f><v>42</v></c></row>'
        "</sheetData></worksheet>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
