"""Write PNG PWA/favicon icons for docs/dashboard (stdlib only).

Renders the same mark as docs/dashboard/icons/app-icon.svg: slate background,
diagonal trend stroke, orange dot — so tabs, manifest, and README PNGs match.
"""
from __future__ import annotations

import binascii
import math
import struct
import zlib
from pathlib import Path


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _write_rgba_png(path: Path, width: int, height: int, rgba_pixels: bytes) -> None:
    """rgba_pixels: width*height*4 row-major RGBA8."""
    if len(rgba_pixels) != width * height * 4:
        raise ValueError("pixel buffer size mismatch")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + rgba_pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    compressed = zlib.compress(raw, 9)
    blob = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def raster_trend_icon(size: int) -> bytes:
    """Match app-icon.svg geometry (viewBox 512)."""
    px = bytearray(size * size * 4)
    bg = (0x0F, 0x17, 0x2A, 0xFF)
    for i in range(0, len(px), 4):
        px[i : i + 4] = bytes(bg)

    s = size / 512.0
    x1, y1 = 108.0 * s, 392.0 * s
    x2, y2 = 372.0 * s, 128.0 * s
    stroke = max(2.0, 72.0 * s)
    cx, cy = 372.0 * s, 128.0 * s
    cr = max(2.0, 56.0 * s)
    vx, vy = x2 - x1, y2 - y1
    l2 = vx * vx + vy * vy

    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= cr * cr:
                px[i : i + 4] = bytes([0xEA, 0x58, 0x0C, 0xFF])
                continue
            if l2 < 1e-6:
                dist = math.hypot(x - x1, y - y1)
            else:
                t = max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / l2))
                qx, qy = x1 + t * vx, y1 + t * vy
                dist = math.hypot(x - qx, y - qy)
            if dist <= stroke / 2.0:
                px[i : i + 4] = bytes([0xF1, 0xF5, 0xF9, 0xFF])

    return bytes(px)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "icons"
    for dim in (32, 192, 512):
        _write_rgba_png(root / f"icon-{dim}.png", dim, dim, raster_trend_icon(dim))
    print("Wrote", root / "icon-32.png", root / "icon-192.png", root / "icon-512.png")


if __name__ == "__main__":
    main()
