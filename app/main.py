"""
지문 → 워크북 사이트 백엔드.

- Gemini 호출은 브라우저에서 사용자 자신의 API 키로 직접 함 (이 서버는 API 키를 보관하지 않음).
- 이 서버가 하는 일은 두 가지뿐:
  1. 정적 프론트엔드(index.html, workbook-generator.js, workbook-renderer.js) 서빙
  2. 완성된 워크북 HTML을 받아서 wkhtmltopdf로 PDF 변환해서 돌려주기
"""

import subprocess
import tempfile
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Workbook Generator")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class RenderRequest(BaseModel):
    html: str
    filename: str = "workbook.pdf"


@app.post("/api/render-pdf")
def render_pdf(req: RenderRequest):
    """워크북 HTML 문자열을 받아 wkhtmltopdf로 PDF를 만들어 반환한다."""
    work_id = uuid.uuid4().hex
    html_path = os.path.join(tempfile.gettempdir(), f"{work_id}.html")
    pdf_path = os.path.join(tempfile.gettempdir(), f"{work_id}.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(req.html)

    try:
        subprocess.run(
            [
                "wkhtmltopdf",
                "--enable-local-file-access",
                "--encoding",
                "utf-8",
                html_path,
                pdf_path,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF 변환 실패: {e.stderr.decode('utf-8', errors='ignore')}",
        )
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF 파일 생성 실패")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=req.filename,
        background=None,
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# 정적 파일(프론트엔드)은 항상 마지막에 mount — API 라우트보다 뒤에 있어야 함
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
