"""Deterministic corruptions and single-image measurements at a fixed analysis scale."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from scipy import ndimage

SIZE = 128
VARIANTS = [("clean", 0)] + [
    (k, s) for k in ("blur", "dark", "bright", "framing", "hair") for s in (1, 2, 3)
]
STRENGTHS = {
    "blur": [0.6, 2.0, 4.0],  # Gaussian radius, pixels at analysis resolution
    "dark": [0.8, 0.4, 0.15],  # linear RGB brightness factor (not camera EV)
    "bright": [1.15, 1.8, 2.8],
    "framing": [0.1, 0.3, 0.55],  # fraction of field shifted out, black padding
    "hair": [3, 12, 28],  # synthetic dark lines; widths 1, 2, 3 pixels
}


def load_image(path: str | Path) -> Image.Image:
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        if min(image.size) < 64:
            raise ValueError("image too small: both dimensions must be at least 64 pixels")
        # Preserve the whole field of view, deliberately normalize aspect ratio.
        return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def degrade(image: Image.Image, kind: str, strength: int, seed: int = 42) -> Image.Image:
    if (kind, strength) not in VARIANTS:
        raise ValueError(f"unknown degradation: {kind}/{strength}")
    out = image.copy()
    if kind == "clean":
        return out
    value = STRENGTHS[kind][strength - 1]
    if kind == "blur":
        return out.filter(ImageFilter.GaussianBlur(value))
    if kind in ("dark", "bright"):
        return ImageEnhance.Brightness(out).enhance(value)
    if kind == "framing":
        shift = round(value * out.width)
        canvas = Image.new("RGB", out.size, "black")
        canvas.paste(out, (shift, 0))
        return canvas
    rng = np.random.default_rng(seed)
    draw = ImageDraw.Draw(out)
    for _ in range(value):
        # Cross-field lines, with independently seeded positions for every source.
        coords = (0, int(rng.integers(out.height)), out.width - 1, int(rng.integers(out.height)))
        draw.line(coords, fill=(12, 9, 8), width=strength)
    return out


def features(image: Image.Image) -> dict[str, float]:
    rgb = np.asarray(image.convert("RGB"), dtype=float) / 255.0
    gray = rgb @ np.array([0.299, 0.587, 0.114])
    hist = np.histogram(gray, bins=32, range=(0, 1))[0] / gray.size
    nonzero = hist[hist > 0]
    # Closing fills thin dark lines. This is a hair proxy, not a hair segmentation mask.
    closing = ndimage.grey_closing(gray, size=(9, 9))
    return {
        "focus": float(np.var(ndimage.laplace(gray)) * 10000),
        "brightness": float(gray.mean()),
        "low_clip": float((gray <= 10 / 255).mean()),
        "high_clip": float((gray >= 245 / 255).mean()),
        "coverage": float((rgb.max(axis=2) > 12 / 255).mean()),
        "contrast": float(gray.std()),
        "hair_response": float(np.mean(closing - gray)),
        "entropy": float(-(nonzero * np.log2(nonzero)).sum()),
    }


def quality_vector(image: Image.Image) -> np.ndarray:
    f = features(image)
    f["focus"] = np.log1p(f["focus"])
    return np.array(list(f.values()))


def lesion_vector(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=float) / 255.0
    hist = np.concatenate(
        [
            np.histogram(rgb[:, :, c], bins=16, range=(0, 1))[0] / (rgb.shape[0] * rgb.shape[1])
            for c in range(3)
        ]
    )
    spatial = np.asarray(image.resize((4, 4), Image.Resampling.BOX), dtype=float).ravel() / 255
    return np.concatenate([hist, spatial])
