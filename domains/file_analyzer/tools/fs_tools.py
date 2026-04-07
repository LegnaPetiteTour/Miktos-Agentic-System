"""
Filesystem tools for the file analyzer domain.
"""

import hashlib
import mimetypes
from pathlib import Path
from engine.tools.base_tool import BaseTool


class FileScannerTool(BaseTool):
    name = "file_scanner"
    description = "Recursively scans a directory and returns file metadata."

    def run(self, input: dict) -> dict:
        root = Path(input["root_path"])
        if not root.exists():
            raise ValueError(f"Path does not exist: {root}")

        files = []
        for path in root.rglob("*"):
            if path.is_file():
                mime, _ = mimetypes.guess_type(str(path))
                files.append({
                    "path": str(path),
                    "name": path.name,
                    "stem": path.stem,
                    "suffix": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                    "mime_type": mime or "unknown",
                    "parent": str(path.parent),
                })

        return {"files": files, "count": len(files)}


class FileHashTool(BaseTool):
    name = "file_hash"
    description = "Computes MD5 hash of a file for duplicate detection."

    def run(self, input: dict) -> dict:
        path = Path(input["path"])
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return {"path": str(path), "md5": hasher.hexdigest()}
