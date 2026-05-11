from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.import_batch import ImportBatch  # noqa: E402
from app.services.internal_service import confirm_import  # noqa: E402


MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _natural_key(path: Path) -> tuple:
    parts = re.split(r"(\d+)", path.name.lower())
    key: list[object] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part)
    return tuple(key)


def _derive_vm_code(folder_name: str) -> str | None:
    m = re.search(r"\b(vm\d+)\b", folder_name, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _ocr_image(path: Path) -> str:
    proc = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "4"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or "").strip()


def _to_mmddyyyy(raw: str, year: int = 2026) -> str | None:
    m = re.fullmatch(r"([A-Za-z]{3})\s+(\d{1,2})", raw.strip())
    if not m:
        return None
    mon = MONTHS.get(m[1].lower())
    if not mon:
        return None
    return f"{mon:02d}/{int(m[2]):02d}/{year}"


def _extract_period(text: str) -> str | None:
    m = re.search(r"Custom\s*\(([^)]+)\)", text, re.IGNORECASE)
    if m:
        return f"Custom ({m[1].strip()})"
    m = re.search(r"([A-Za-z]{3}\s+\d{1,2})\s*-\s*([A-Za-z]{3}\s+\d{1,2})", text)
    if m:
        left = _to_mmddyyyy(m[1])
        right = _to_mmddyyyy(m[2])
        if left and right:
            return f"Custom ({left} - {right})"
        return f"{m[1]} - {m[2]}"

    dates = re.findall(r"\b([A-Za-z]{3}\s+\d{1,2})\b", text)
    if len(dates) >= 2:
        left = _to_mmddyyyy(dates[0])
        right = _to_mmddyyyy(dates[-1])
        if left and right:
            return f"Custom ({left} - {right})"
    return None


def _parse_money(token: str) -> float | None:
    token = token.replace(",", "").strip()
    token = token.lstrip("$")
    if token in {"", "O", "o", "(0)", "(O)"}:
        return 0.0
    try:
        return float(token)
    except ValueError:
        return None


def _parse_int(token: str) -> int | None:
    token = token.strip()
    if token in {"O", "o", "(0)", "(O)", "[0]"}:
        return 0
    token = token.replace(",", "")
    try:
        return int(float(token))
    except ValueError:
        return None


def _extract_summary_values(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header_idx = None
    for idx, line in enumerate(lines):
        if re.search(r"\bviews\b", line, re.IGNORECASE) and re.search(r"\bclicks\b", line, re.IGNORECASE):
            header_idx = idx
            break

    value_line = None
    if header_idx is not None:
        for line in lines[header_idx + 1 : header_idx + 4]:
            if re.search(r"[\d$]", line):
                value_line = line
                break
    if value_line is None:
        for line in lines:
            if line.count("$") >= 2 or len(re.findall(r"\d+", line)) >= 4:
                value_line = line
                break

    values = []
    if value_line:
        tokens = re.findall(r"\$\d+(?:\.\d+)?|\d+(?:\.\d+)?|\([0Oo]\)|[Oo]", value_line)
        for token in tokens:
            if token.startswith("$") or re.fullmatch(r"\d+\.\d+", token) or token.isdigit():
                parsed = _parse_money(token)
                if parsed is not None:
                    values.append(parsed)
            else:
                values.append(0.0)

    views = int(values[0]) if len(values) > 0 else 0
    clicks = int(values[1]) if len(values) > 1 else 0
    orders = int(values[2]) if len(values) > 2 else 0
    revenue = float(values[3]) if len(values) > 3 else 0.0
    spend = float(values[4]) if len(values) > 4 else 0.0
    roas = float(values[5]) if len(values) > 5 else (round(revenue / spend, 2) if spend else 0.0)

    return {
        "views": views,
        "clicks": clicks,
        "orders": orders,
        "revenue": revenue,
        "spend": spend,
        "roas": roas,
    }


def _extract_listing_row(path: Path, text: str, no_vm: str | None) -> tuple[dict | None, str | None]:
    compact = " ".join(text.split())
    listing_id_match = re.search(r"listing/(\d{6,})", compact)
    if not listing_id_match:
        listing_id_match = re.search(r"\b(\d{6,})\?ref=dashboard-tabs\b", compact)
    if not listing_id_match:
        return None, "missing listing_id"

    listing_id = listing_id_match.group(1)
    period = _extract_period(text)
    if not period:
        return None, f"{path.name}: missing period"

    title = None
    title_match = re.search(
        r"in stock\s+(.+?)\s+Lifetime ad orders:",
        compact,
        re.IGNORECASE,
    )
    if title_match:
        title = title_match.group(1).strip(" -|")

    price = None
    stock = None
    price_stock = re.search(
        r"\$(\d+(?:\.\d+)?)\s+(\d+)\s+in stock",
        compact,
        re.IGNORECASE,
    )
    if price_stock:
        price = float(price_stock.group(1))
        stock = int(price_stock.group(2))

    lifetime_orders = None
    m = re.search(r"Lifetime ad orders:\s*(\d+)", compact, re.IGNORECASE)
    if m:
        lifetime_orders = int(m.group(1))

    lifetime_revenue = None
    m = re.search(r"Lifetime ad revenue:\s*\$?([\d.,]+)", compact, re.IGNORECASE)
    if m:
        try:
            lifetime_revenue = float(m.group(1).replace(",", ""))
        except ValueError:
            lifetime_revenue = None

    summary = _extract_summary_values(text)

    return {
        "listing_id": listing_id,
        "title": title,
        "no_vm": no_vm,
        "price": price,
        "stock": stock,
        "category": None,
        "lifetime_orders": lifetime_orders,
        "lifetime_revenue": lifetime_revenue,
        "period": period,
        **summary,
    }, None


async def _run(folder: Path, batch_id: str, no_vm: str | None) -> int:
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp"}
    image_paths = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed_exts],
        key=_natural_key,
    )
    if not image_paths:
        raise SystemExit(f"No supported images found in {folder}")

    rows: list[dict] = []
    errors: list[str] = []
    seen: dict[tuple[str, str], dict] = {}
    successful_files: list[str] = []
    failed_files: list[str] = []

    for path in image_paths:
        text = _ocr_image(path)
        row, err = _extract_listing_row(path, text, no_vm)
        if err:
            errors.append(err)
            failed_files.append(path.name)
            continue
        key = (row["listing_id"], row["period"])
        seen[key] = row
        successful_files.append(path.name)

    rows = list(seen.values())

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        existing = result.scalar_one_or_none()
        if existing:
            raise SystemExit(f"Batch already exists: {batch_id}")

        batch = ImportBatch(
            batch_id=batch_id,
            status="extracted",
            file_count=len(image_paths),
            total_files=len(image_paths),
            progress=len(successful_files),
            listing_count=len(rows),
            keyword_count=0,
            note=f"OCR import from local folder: {folder}",
            preview_data={
                "batch_id": batch_id,
                "listing_report": rows,
                "keyword_report": [],
                "successful_files": successful_files,
                "failed_files": failed_files,
                "extraction_errors": {name: "OCR parse failed" for name in failed_files},
                "quota_exhausted": False,
                "streaming": False,
                "ocr_mode": True,
                "source_folder": str(folder),
            },
        )
        db.add(batch)
        await db.commit()

        if not rows:
            print(f"Batch {batch_id} created, but OCR found no rows.")
            print(f"Failed files: {len(failed_files)}")
            return 1

        result = await confirm_import(
            batch_id=batch_id,
            listing_report=rows,
            keyword_report=[],
            no_vm=no_vm,
            db=db,
        )

        print(f"Batch: {batch_id}")
        print(f"Listing rows: {result['rows']['listing']}")
        print("Keyword rows: 0")
        print(f"Successful files: {len(successful_files)}")
        print(f"Failed files: {len(failed_files)}")
        if errors:
            print("Some files were skipped:")
            for err in errors[:10]:
                print(f" - {err}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR import screenshots from a local raw/internal folder.")
    parser.add_argument("--folder", required=True, help="Path to the raw/internal batch folder.")
    parser.add_argument("--no-vm", default=None, help="Optional VM code override.")
    parser.add_argument("--batch-id", default=None, help="Optional import batch id override.")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")

    no_vm = args.no_vm or _derive_vm_code(folder.name)
    if not no_vm:
        raise SystemExit("Could not derive VM code from folder name. Pass --no-vm VM01.")

    batch_id = args.batch_id or f"OCR_{folder.name}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    if len(batch_id) > 32:
        batch_id = batch_id[:32]

    print(f"Importing folder: {folder}")
    print(f"VM code: {no_vm}")
    print(f"Batch id: {batch_id}")
    return asyncio.run(_run(folder, batch_id, no_vm))


if __name__ == "__main__":
    raise SystemExit(main())
