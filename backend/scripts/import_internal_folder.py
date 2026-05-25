from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.import_batch import ImportBatch  # noqa: E402
from app.services.EtseeMate_service import (  # noqa: E402
    confirm_import,
    run_extraction,
    save_uploaded_files,
    validate_image,
)


def _natural_key(path: Path) -> tuple:
    parts = re.split(r"(\d+)", path.name.lower())
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return tuple(key)


def _derive_vm_code(folder_name: str) -> str | None:
    m = re.search(r"\b(vm\d+)\b", folder_name, re.IGNORECASE)
    return m.group(1).upper() if m else None


async def _load_folder(folder: Path, no_vm: str | None, confirm_batch: bool) -> int:
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp"}
    image_paths = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed_exts],
        key=_natural_key,
    )
    if not image_paths:
        raise SystemExit(f"No supported images found in {folder}")

    file_entries: list[tuple[SimpleNamespace, bytes]] = []
    skipped: list[str] = []
    for path in image_paths:
        content = path.read_bytes()
        err = await validate_image(path.name, content)
        if err:
            skipped.append(err)
            continue
        file_entries.append((SimpleNamespace(filename=path.name), content))

    if skipped:
        print("Validation warnings:")
        for item in skipped:
            print(f" - {item}")

    if not file_entries:
        raise SystemExit("All files failed validation; nothing to import.")

    async with AsyncSessionLocal() as db:
        batch_id, count, _ = await save_uploaded_files(file_entries, db)

        result = await db.execute(select(ImportBatch).where(ImportBatch.batch_id == batch_id))
        batch = result.scalar_one()
        batch.note = f"Imported from local folder: {folder}"
        await db.commit()

        preview = await run_extraction(batch_id, db)
        batch_status = preview.get("batch_id", batch_id)
        print(f"Batch: {batch_status}")
        print(f"Listing rows: {len(preview.get('listing_report', []))}")
        print(f"Keyword rows: {len(preview.get('keyword_report', []))}")

        if not confirm_batch:
            print("Confirm step skipped.")
            return 0

        if preview.get("listing_report") or preview.get("keyword_report"):
            confirm_result = await confirm_import(
                batch_id=batch_id,
                listing_report=preview.get("listing_report", []),
                keyword_report=preview.get("keyword_report", []),
                no_vm=no_vm,
                db=db,
            )
            print(
                "Confirmed import:",
                f"{confirm_result['rows']['listing']} listing rows,",
                f"{confirm_result['rows']['keyword']} keyword rows",
            )
        else:
            print("No extracted rows to confirm.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import screenshots from a local raw/EtseeMate folder.")
    parser.add_argument(
        "--folder",
        required=True,
        help="Path to the raw/EtseeMate batch folder, e.g. ../data/raw/EtseeMate/04-05-2026-VM01",
    )
    parser.add_argument(
        "--no-vm",
        default=None,
        help="Optional VM code override. Defaults to extracting VMxx from the folder name.",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Stop after extraction and do not write to manual_*_report tables.",
    )
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")

    no_vm = args.no_vm or _derive_vm_code(folder.name)
    if not no_vm:
        raise SystemExit("Could not derive VM code from folder name. Pass --no-vm VM01.")

    print(f"Importing folder: {folder}")
    print(f"VM code: {no_vm}")
    return asyncio.run(_load_folder(folder, no_vm=no_vm, confirm_batch=not args.no_confirm))


if __name__ == "__main__":
    raise SystemExit(main())
