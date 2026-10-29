import runpy
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from closed_review.errors import ReviewError


def test_korean_view_requires_complete_translations_and_escapes_input():
    script = runpy.run_path("scripts/render-korean-audit.py")
    source = "# Synthetic\n\nA quoted sentence.\n\n## References\n\nExample reference.\n"
    finding = {
        "id": "F1",
        "model_severity": "minor",
        "evidence": [{"source_id": "manuscript", "quote": "A quoted sentence."}],
        "flaw_checks": [],
    }
    scan = {"review": {"findings": [finding]}}
    translation = {
        "source_sha256": "same-hash",
        "paragraphs": {"1": "# 합성 원고", "3": "인용된 문장.", "5": "## 참고 문헌"},
        "findings": {"F1": {"issue": "<script>나쁜 입력</script>", "why": "이유", "checks": []}},
    }
    view = script["render"](source, scan, translation, "same-hash", "ms1-r1")
    assert 'lang="ko"' in view
    assert "&lt;script&gt;나쁜 입력&lt;/script&gt;" in view
    assert "<script>" not in view
    assert 'href="#ko-3"' in view
    assert "인용된 문장." in view
    assert "A quoted sentence." in view
    assert "Example reference." in view
    assert "answer-key.html" not in view
    with pytest.raises(ReviewError, match="different manuscript"):
        script["render"](source, scan, translation, "different-hash", "ms1-r1")
    translation["paragraphs"].pop("3")
    with pytest.raises(ReviewError, match="missing manuscript translations"):
        script["render"](source, scan, translation, "same-hash", "ms1-r1")


def test_audit_server_exposes_only_page_and_is_read_only():
    script = runpy.run_path("scripts/serve-audit-view.py")
    server = script["make_server"]("127.0.0.1", 0, b"synthetic test page")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(base + "/", timeout=5) as response:
            assert response.read() == b"synthetic test page"
            assert response.headers["Cache-Control"] == "no-store"
            assert "default-src 'none'" in response.headers["Content-Security-Policy"]
        for route in ("/answer-key.html", "/scan.json", "/../anything"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + route, timeout=5)
            assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + "/", data=b"change", method="POST"), timeout=5)
        assert error.value.code == 405
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
