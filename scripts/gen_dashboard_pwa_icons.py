"""Write simple solid PNGs for docs/dashboard PWA icons (stdlib only)."""
from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_rgba_png(path: Path, width: int, height: int, rgba: tuple[int, int, int, int]) -> None:
    """8-bit RGBA PNG, filter type 0 per scanline."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    px = bytes(rgba)
    raw = b"".join(b"\x00" + px * width for _ in range(height))
    compressed = zlib.compress(raw, 9)
    blob = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "icons"
    # Brand-adjacent blue; full-bleed works as maskable baseline.
    color = (0x2D, 0x62, 0xFF, 0xFF)
    write_rgba_png(root / "icon-192.png", 192, 192, color)
    write_rgba_png(root / "icon-512.png", 512, 512, color)


if __name__ == "__main__":
    main()
