#!/usr/bin/env python3
"""Generate Parivar Saathi Android and PWA brand assets using only stdlib."""

from __future__ import annotations

import argparse
import struct
import zlib
from collections import deque
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "code/parivar_saathi_android_app/branding/source/Parivar_Saathi_Logo.png"
ANDROID_RES = ROOT / "code/parivar_saathi_android_app/android/app/src/main/res"
PWA_ASSETS = ROOT / "code/tools/sim/pwa/assets"
BACKGROUND = (245, 251, 247)


def read_rgb_png(path: Path) -> tuple[int, int, list[bytearray]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG: {path}")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        content = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", content
            )
            if compression != 0 or filtering != 0:
                raise ValueError("unsupported PNG compression/filter method")
        elif kind == b"IDAT":
            compressed.extend(content)
        elif kind == b"IEND":
            break
    if (bit_depth, color_type, interlace) != (8, 2, 0):
        raise ValueError("source must be a non-interlaced 8-bit RGB PNG")
    assert width is not None and height is not None
    raw = zlib.decompress(compressed)
    stride = width * 3
    rows: list[bytearray] = []
    pos = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        scan = bytearray(raw[pos : pos + stride])
        pos += stride
        for i in range(stride):
            left = scan[i - 3] if i >= 3 else 0
            above = previous[i]
            upper_left = previous[i - 3] if i >= 3 else 0
            if filter_type == 1:
                scan[i] = (scan[i] + left) & 255
            elif filter_type == 2:
                scan[i] = (scan[i] + above) & 255
            elif filter_type == 3:
                scan[i] = (scan[i] + ((left + above) // 2)) & 255
            elif filter_type == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
                scan[i] = (scan[i] + predictor) & 255
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter: {filter_type}")
        rows.append(scan)
        previous = scan
    if pos != len(raw):
        raise ValueError("unexpected trailing source PNG data")
    return width, height, rows


def png_chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def write_rgba_png(path: Path, width: int, height: int, pixels: bytes, compression: int = 9) -> None:
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA pixel buffer has the wrong size")
    stride = width * 4
    encoded = bytearray()
    previous = bytearray(stride)
    for y in range(height):
        row = pixels[y * stride : (y + 1) * stride]
        best_score, best_filter, best_data = None, 0, row
        for filter_type in range(5):
            filtered = bytearray(stride)
            score = 0
            for i, value in enumerate(row):
                left = row[i - 4] if i >= 4 else 0
                above = previous[i]
                upper_left = previous[i - 4] if i >= 4 else 0
                if filter_type == 0:
                    predictor = 0
                elif filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = above
                elif filter_type == 3:
                    predictor = (left + above) // 2
                else:
                    p = left + above - upper_left
                    pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                    predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
                residual = (value - predictor) & 255
                filtered[i] = residual
                score += abs(residual if residual < 128 else residual - 256)
            if best_score is None or score < best_score:
                best_score, best_filter, best_data = score, filter_type, filtered
        encoded.append(best_filter)
        encoded.extend(best_data)
        previous = bytearray(row)
    raw = bytes(encoded)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    payload = PNG_SIGNATURE + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", zlib.compress(raw, compression)) + png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def crop_with_transparency(
    rows: list[bytearray],
    source_width: int,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    min_channel: int,
    max_spread: int,
) -> tuple[int, int, bytearray]:
    if x < 0 or y < 0 or x + width > source_width or y + height > len(rows):
        raise ValueError("crop is outside the source image")
    rgb = bytearray(width * height * 3)
    for cy in range(height):
        src = rows[y + cy]
        start = cy * width * 3
        rgb[start : start + width * 3] = src[x * 3 : (x + width) * 3]
    transparent = bytearray(width * height)
    queue: deque[int] = deque()

    def candidate(index: int) -> bool:
        r, g, b = rgb[index * 3 : index * 3 + 3]
        return min(r, g, b) >= min_channel and max(r, g, b) - min(r, g, b) <= max_spread

    def add_edge(index: int) -> None:
        if not transparent[index] and candidate(index):
            transparent[index] = 1
            queue.append(index)

    for cx in range(width):
        add_edge(cx)
        add_edge((height - 1) * width + cx)
    for cy in range(height):
        add_edge(cy * width)
        add_edge(cy * width + width - 1)

    while queue:
        index = queue.popleft()
        cx, cy = index % width, index // width
        if cx and not transparent[index - 1] and candidate(index - 1):
            transparent[index - 1] = 1
            queue.append(index - 1)
        if cx + 1 < width and not transparent[index + 1] and candidate(index + 1):
            transparent[index + 1] = 1
            queue.append(index + 1)
        if cy and not transparent[index - width] and candidate(index - width):
            transparent[index - width] = 1
            queue.append(index - width)
        if cy + 1 < height and not transparent[index + width] and candidate(index + width):
            transparent[index + width] = 1
            queue.append(index + width)

    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        rgb_start, rgba_start = i * 3, i * 4
        rgba[rgba_start : rgba_start + 3] = rgb[rgb_start : rgb_start + 3]
        rgba[rgba_start + 3] = 0 if transparent[i] else 255
    return width, height, rgba


def resize_rgba(source: tuple[int, int, bytearray], width: int, height: int) -> bytearray:
    sw, sh, pixels = source
    out = bytearray(width * height * 4)
    for y in range(height):
        fy = (y + 0.5) * sh / height - 0.5
        y0 = max(0, min(sh - 1, int(fy)))
        y1 = min(sh - 1, y0 + 1)
        wy = max(0.0, min(1.0, fy - y0))
        for x in range(width):
            fx = (x + 0.5) * sw / width - 0.5
            x0 = max(0, min(sw - 1, int(fx)))
            x1 = min(sw - 1, x0 + 1)
            wx = max(0.0, min(1.0, fx - x0))
            weights = ((1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy)
            indices = ((y0 * sw + x0) * 4, (y0 * sw + x1) * 4, (y1 * sw + x0) * 4, (y1 * sw + x1) * 4)
            out_index = (y * width + x) * 4
            a_sum = sum(pixels[i + 3] * w for i, w in zip(indices, weights))
            if a_sum <= 0:
                continue
            for channel in range(3):
                value = sum(pixels[i + channel] * pixels[i + 3] * w for i, w in zip(indices, weights)) / a_sum
                out[out_index + channel] = max(0, min(255, round(value)))
            out[out_index + 3] = max(0, min(255, round(a_sum)))
    return out


def resize_contained(mark: tuple[int, int, bytearray], canvas_size: int, fraction: float) -> bytearray:
    side = round(canvas_size * fraction)
    resized = resize_rgba(mark, side, side)
    out = bytearray(canvas_size * canvas_size * 4)
    pad = (canvas_size - side) // 2
    for y in range(side):
        src_start = y * side * 4
        dst_start = ((y + pad) * canvas_size + pad) * 4
        out[dst_start : dst_start + side * 4] = resized[src_start : src_start + side * 4]
    return out


def composite_background(transparent_icon: bytes, size: int, *, circle: bool = False) -> bytes:
    out = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            if circle and (x + 0.5 - size / 2) ** 2 + (y + 0.5 - size / 2) ** 2 > (size * 0.5) ** 2:
                continue
            a = transparent_icon[i + 3] / 255.0
            for c in range(3):
                out[i + c] = round(transparent_icon[i + c] * a + BACKGROUND[c] * (1 - a))
            out[i + 3] = 255
    return bytes(out)


def transparent_monochrome(icon: bytes) -> bytes:
    result = bytearray(len(icon))
    for index in range(0, len(icon), 4):
        result[index : index + 3] = b"\xff\xff\xff"
        result[index + 3] = icon[index + 3]
    return bytes(result)


def write_mark_source_logo(rows: list[bytearray], width: int) -> tuple[int, int, bytearray]:
    # The approved composition places the family/home/shield mark in this top square.
    return crop_with_transparency(rows, width, 277, 137, 700, 700, min_channel=150, max_spread=140)


def write_wordmark(rows: list[bytearray], width: int) -> tuple[int, int, bytearray]:
    # Retain the complete supplied wordmark, underline and tagline for splash branding.
    return crop_with_transparency(rows, width, 88, 878, 1080, 292, min_channel=235, max_spread=42)


def generate() -> list[Path]:
    width, height, rows = read_rgb_png(SOURCE)
    if (width, height) != (1254, 1254):
        raise ValueError(f"unexpected approved logo dimensions: {width}x{height}")
    mark = write_mark_source_logo(rows, width)
    wordmark = write_wordmark(rows, width)
    outputs: list[Path] = []

    android_drawable = ANDROID_RES / "drawable-nodpi"
    path = android_drawable / "ic_launcher_foreground.png"
    write_rgba_png(path, 432, 432, resize_contained(mark, 432, 0.63))
    outputs.append(path)
    path = android_drawable / "ic_launcher_monochrome.png"
    write_rgba_png(path, 432, 432, transparent_monochrome(resize_contained(mark, 432, 0.63)))
    outputs.append(path)
    path = android_drawable / "ic_stat_parivar_saathi.png"
    mono_96 = transparent_monochrome(resize_contained(mark, 96, 0.86))
    write_rgba_png(path, 96, 96, mono_96)
    outputs.append(path)
    wordmark_width = 720  # xhdpi resource: 360dp wide on device
    wordmark_height = round(wordmark_width * 292 / 1080)
    wordmark_sized = resize_rgba(wordmark, wordmark_width, wordmark_height)
    path = ANDROID_RES / "drawable-xhdpi/parivar_saathi_splash_wordmark.png"
    write_rgba_png(path, wordmark_width, wordmark_height, wordmark_sized)
    outputs.append(path)

    for density, size in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        for suffix, circle in (("", False), ("_round", True)):
            path = ANDROID_RES / f"mipmap-{density}" / f"ic_launcher{suffix}.png"
            contained = resize_contained(mark, size, 0.84)
            write_rgba_png(path, size, size, composite_background(contained, size, circle=circle))
            outputs.append(path)

    path = PWA_ASSETS / "parivar-saathi-icon-192.png"
    write_rgba_png(path, 192, 192, composite_background(resize_contained(mark, 192, 0.84), 192))
    outputs.append(path)
    path = PWA_ASSETS / "parivar-saathi-icon-maskable-512.png"
    write_rgba_png(path, 512, 512, composite_background(resize_contained(mark, 512, 0.66), 512))
    outputs.append(path)
    svg_path = PWA_ASSETS / "icon.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<image href="parivar-saathi-icon-192.png" width="512" height="512"/></svg>\n',
        encoding="utf-8",
    )
    outputs.append(svg_path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="check expected resources exist without rewriting them")
    args = parser.parse_args()
    required = [
        ANDROID_RES / "drawable-nodpi/ic_launcher_foreground.png",
        ANDROID_RES / "drawable-nodpi/ic_launcher_monochrome.png",
        ANDROID_RES / "drawable-nodpi/ic_stat_parivar_saathi.png",
        ANDROID_RES / "drawable-xhdpi/parivar_saathi_splash_wordmark.png",
        *[ANDROID_RES / f"mipmap-{density}/ic_launcher.png" for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")],
        *[ANDROID_RES / f"mipmap-{density}/ic_launcher_round.png" for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")],
        PWA_ASSETS / "parivar-saathi-icon-192.png",
        PWA_ASSETS / "parivar-saathi-icon-maskable-512.png",
        PWA_ASSETS / "icon.svg",
    ]
    if args.check:
        missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
        if missing:
            print("MISSING " + ", ".join(missing))
            return 1
        print(f"PASS: {len(required)} generated PNG assets exist")
        return 0
    if not SOURCE.is_file():
        parser.error(f"approved source logo is missing: {SOURCE}")
    output_paths = generate()
    print(f"PASS: generated {len(output_paths)} Android and PWA PNG assets from {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
