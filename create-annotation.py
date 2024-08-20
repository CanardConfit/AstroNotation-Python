import math
import os
import sys
import time
import numpy
import piexif
import utils
from PIL import Image, ImageDraw, ImageFont
from astropy.io import fits
from astropy.io.fits import Header
from datetime import datetime

padding = 20

def fits_to_jpg(fits_file):
    with fits.open(fits_file) as hdul:
        red_data = hdul[0].data[0]
        green_data = hdul[0].data[1]
        blue_data = hdul[0].data[2]

        red_data = numpy.nan_to_num(red_data)
        red_data = (red_data - numpy.min(red_data)) / (numpy.max(red_data) - numpy.min(red_data)) * 255
        red_data = red_data.astype(numpy.uint8)

        green_data = numpy.nan_to_num(green_data)
        green_data = (green_data - numpy.min(green_data)) / (numpy.max(green_data) - numpy.min(green_data)) * 255
        green_data = green_data.astype(numpy.uint8)

        blue_data = numpy.nan_to_num(blue_data)
        blue_data = (blue_data - numpy.min(blue_data)) / (numpy.max(blue_data) - numpy.min(blue_data)) * 255
        blue_data = blue_data.astype(numpy.uint8)

        rgb_image = numpy.stack((red_data, green_data, blue_data), axis=-1)

        image = Image.fromarray(rgb_image)

        flipped_image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        return flipped_image, hdul[0].header


def annotate_image(img: Image, image_path: str, metadata: Header, meta: utils.Meta):
    draw = ImageDraw.Draw(img)

    font_path = "C:/Windows/Fonts/arial.ttf"
    font_size = 100
    font = ImageFont.truetype(font_path, font_size)

    img_width, img_height = img.size

    inter_line = 20

    seconds_expose = int(metadata["EXPTIME"]) * int(metadata["STACKCNT"])
    exposure = time.strftime("%H:%M:%S", time.gmtime(seconds_expose))

    text = (
        f"{str(metadata["OBJECT"])} - {meta.idName}, ra: {float(metadata["CRVAL1"]):0.3f}° dec: {float(metadata["CRVAL2"]):0.3f}°",
        f"{datetime.fromisoformat(str(metadata["DATE-OBS"])).date()} - {int(math.floor(float(metadata["FOCALLEN"])))}mm, {exposure} stack - {str(metadata["INSTRUME"])}",
        f"{meta.author} - {meta.locationName}"
    )

    x = padding
    y = img_height - len(text) * font_size - padding - len(text) * inter_line

    for i, t in enumerate(text):
        draw.text((x, y + i * font_size + i * inter_line), t, font=font, fill="white")

    exif_dict = {
        "0th": {},
        "Exif": {},
        "GPS": {}
    }

    date_obs = datetime.fromisoformat(str(metadata["DATE-OBS"])).strftime("%Y:%m:%d %H:%M:%S")

    exif_dict["0th"][piexif.ImageIFD.Model] = str(metadata["INSTRUME"])
    exif_dict["0th"][piexif.ImageIFD.Artist] = meta.author
    exif_dict["0th"][piexif.ImageIFD.Copyright] = meta.author
    exif_dict["0th"][piexif.ImageIFD.DateTime] = date_obs
    exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = (int(seconds_expose), 1)
    exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (int(math.floor(float(metadata["FOCALLEN"]))), 1)
    exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings] = int(metadata["GAIN"])
    exif_dict["Exif"][piexif.ExifIFD.ExifVersion] = b"0231"
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_obs
    exif_dict["Exif"][piexif.ExifIFD.LensModel] = meta.lensModel

    latitude = float(metadata["SITELAT"])
    longitude = float(metadata["SITELONG"])

    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = utils.convert_to_dms(latitude)
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = utils.convert_to_dms(longitude)

    exif_bytes = piexif.dump(exif_dict)

    img.save(image_path, "JPEG", quality=100, exif=exif_bytes)
    print(f"Image saved as {image_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python annotate_image.py <image_path> <json_meta>")
        sys.exit(1)

    image_path = sys.argv[1]
    json_file_path = sys.argv[2]

    image, headers = fits_to_jpg(image_path)

    meta = utils.load_meta_from_json(json_file_path)

    new_image_path = f"{meta.author}_{datetime.fromisoformat(str(headers["DATE-OBS"])).strftime("%Y-%m")}_{meta.idName.replace(" ", "-")}_annoted.jpg"

    annotate_image(image, new_image_path, headers, meta)