import argparse
import json
import math
import time
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFont
from astropy.io import fits


def find_arial_ttf() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/msttcorefonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/microsoft/Arial.ttf"),
        Path("/usr/share/fonts/truetype/microsoft/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise SystemExit("Arial.ttf not found. Install Arial (or Microsoft core fonts) on your system.")


def fits_rgb_to_image_and_header(fits_path: Path) -> Tuple[Image.Image, Dict[str, Any]]:
    with fits.open(str(fits_path)) as hdul:
        data = hdul[0].data
        hdr = dict(hdul[0].header)

    red = np.nan_to_num(data[0])
    green = np.nan_to_num(data[1])
    blue = np.nan_to_num(data[2])

    red_min, red_max = float(np.min(red)), float(np.max(red))
    green_min, green_max = float(np.min(green)), float(np.max(green))
    blue_min, blue_max = float(np.min(blue)), float(np.max(blue))

    if red_max != red_min:
        red = ((red - red_min) / (red_max - red_min) * 255.0).astype(np.uint8)
    else:
        red = np.zeros(red.shape, dtype=np.uint8)

    if green_max != green_min:
        green = ((green - green_min) / (green_max - green_min) * 255.0).astype(np.uint8)
    else:
        green = np.zeros(green.shape, dtype=np.uint8)

    if blue_max != blue_min:
        blue = ((blue - blue_min) / (blue_max - blue_min) * 255.0).astype(np.uint8)
    else:
        blue = np.zeros(blue.shape, dtype=np.uint8)

    rgb = np.stack((red, green, blue), axis=-1)
    img = Image.fromarray(rgb, mode="RGB")
    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    return img, hdr


def load_input_image_and_metadata(input_path: Path, info_json_path: Optional[Path]) -> Tuple[Image.Image, Dict[str, Any]]:
    ext = input_path.suffix.lower()

    if ext in (".fits", ".fit", ".fts"):
        return fits_rgb_to_image_and_header(input_path)

    if ext in (".jpg", ".jpeg"):
        if info_json_path is None:
            raise SystemExit("For JPG input you must provide --info info.json.")
        with info_json_path.open("r", encoding="utf-8") as f:
            info = json.load(f)
        img = Image.open(str(input_path)).convert("RGB")
        return img, dict(info)

    raise SystemExit(f"Unsupported input extension: {ext} (use FITS or JPG).")


def to_dms_rational(deg: float):
    deg_abs = abs(deg)
    d = int(deg_abs)
    m_float = (deg_abs - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    s_frac = Fraction(s).limit_denominator(10000)
    return ((d, 1), (m, 1), (s_frac.numerator, s_frac.denominator))


def annotate_and_save(img: Image.Image, output_path: Path, md: Dict[str, Any], meta: Dict[str, Any]) -> None:
    draw = ImageDraw.Draw(img)

    arial_path = find_arial_ttf()
    img_w, img_h = img.size

    font_size = int(md.get("font_size", 80))
    font = ImageFont.truetype(str(arial_path), font_size)

    padding = int(md.get("padding", 20))
    inter_line = int(md.get("inter_line"))

    author = str(meta["author"]).strip()
    lens = str(meta.get("lensName", meta.get("lensModel", ""))).strip()
    id_name = str(meta["idName"]).strip()
    location = str(meta["locationName"]).strip()

    obj = str(md.get("OBJECT", md.get("object", "")))
    instr = str(md.get("INSTRUME", md.get("INSTRUMENT", md.get("instrument", ""))))

    ra = float(md.get("RA", md.get("CRVAL1")))
    dec = float(md.get("DEC", md.get("CRVAL2")))

    exptime = float(md["EXPTIME"])
    stackcnt = int(md.get("STACKCNT", 1))
    seconds_total = exptime * stackcnt
    exposure_hms = time.strftime("%H:%M:%S", time.gmtime(int(round(seconds_total))))

    focallen = float(md["FOCALLEN"])
    gain = int(md["GAIN"])

    date_obs = datetime.fromisoformat(str(md["DATE-OBS"])).strftime("%Y:%m:%d %H:%M:%S")
    date_only = date_obs.split(" ")[0].replace(":", "-")

    line1 = f"{obj} - {id_name}, ra: {ra:0.3f}° dec: {dec:0.3f}°"
    line2 = f"{date_only} - {int(math.floor(focallen))}mm, {exposure_hms} stack - {instr}"
    line3 = f"{author} - {location}"
    lines = [line1, line2, line3]

    block_h = len(lines) * font_size + (len(lines) - 1) * inter_line
    x = padding
    y = img_h - block_h - padding

    for i, t in enumerate(lines):
        draw.text((x, y + i * (font_size + inter_line)), t, font=font, fill="white")

    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}

    exif_dict["0th"][piexif.ImageIFD.Model] = instr
    exif_dict["0th"][piexif.ImageIFD.Artist] = author
    exif_dict["0th"][piexif.ImageIFD.Copyright] = author
    exif_dict["0th"][piexif.ImageIFD.DateTime] = date_obs

    exp_frac = Fraction(seconds_total).limit_denominator(1000000)
    exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = (exp_frac.numerator, exp_frac.denominator)
    exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (int(math.floor(focallen)), 1)
    exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings] = gain
    exif_dict["Exif"][piexif.ExifIFD.ExifVersion] = b"0231"
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_obs
    exif_dict["Exif"][piexif.ExifIFD.LensModel] = lens

    lat = float(md.get("SITELAT", md.get("LAT", md.get("LATITUDE"))))
    lon = float(md.get("SITELONG", md.get("LON", md.get("LONGITUDE"))))

    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = "N" if lat >= 0 else "S"
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = to_dms_rational(lat)
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = "E" if lon >= 0 else "W"
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = to_dms_rational(lon)

    exif_bytes = piexif.dump(exif_dict)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=100, exif=exif_bytes)
    print(f"Saved: {output_path}")


def default_output_path(input_path: Path, md: Dict[str, Any], meta: Dict[str, Any]) -> Path:
    date_obs = datetime.fromisoformat(str(md["DATE-OBS"])).strftime("%Y-%m")
    author = str(meta["author"]).strip().replace(" ", "-")
    obj = str(meta["idName"]).strip().replace(" ", "-")
    name = f"{author}_{date_obs}_{obj}_annotated.jpg"
    return input_path.with_name(name)


def main() -> None:
    p = argparse.ArgumentParser(description="Annotate FITS/JPG with metadata and write EXIF (Arial only).")
    p.add_argument("--input", required=True, help="Input image: .fits/.fit/.fts or .jpg/.jpeg")
    p.add_argument("--meta", required=True, help="Meta JSON: author/lensName/idName/locationName")
    p.add_argument("--info", help="Info JSON (required if input is JPG): OBJECT/RA/DEC/EXPTIME/STACKCNT/...")
    p.add_argument("--output", help="Output JPG path (optional). If omitted, a default name is generated.")

    args = p.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    meta_path = Path(args.meta).expanduser().resolve()
    info_path = Path(args.info).expanduser().resolve() if args.info else None
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    img, md = load_input_image_and_metadata(input_path, info_path)

    if output_path is None:
        output_path = default_output_path(input_path, md, meta)

    annotate_and_save(img, output_path, md, meta)


if __name__ == "__main__":
    main()
