import struct
import zlib

import numpy as np

from app.api_terrain import _png_grayscale


def test_lola_preview_png_encoder_returns_grayscale_image():
    encoded = _png_grayscale(np.array([[0.0, 10.0], [20.0, np.nan]], dtype=float))
    assert encoded.startswith(b"\x89PNG\r\n\x1a\n")
    length = struct.unpack(">I", encoded[8:12])[0]
    assert encoded[12:16] == b"IHDR"
    width, height, depth, color_type = struct.unpack(">IIBB", encoded[16:26])
    assert (width, height, depth, color_type) == (2, 2, 8, 0)
    assert length == 13
    idat_start = encoded.index(b"IDAT")
    idat_length = struct.unpack(">I", encoded[idat_start - 4:idat_start])[0]
    pixels = zlib.decompress(encoded[idat_start + 4:idat_start + 4 + idat_length])
    assert pixels[0] == 0 and pixels[1] == 0


def test_lola_preview_png_encoder_rejects_all_nodata():
    try:
        _png_grayscale(np.full((2, 2), np.nan))
    except Exception as error:
        assert "no valid hillshade" in str(error)
    else:
        raise AssertionError("An all-nodata preview must not produce a fabricated image")
