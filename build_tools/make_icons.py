"""Generate the PWA / favicon icons from the 📺 emoji.

Dev-only tool (Pillow lives in the `dev` dependency group). The generated PNGs
and `favicon.ico` are committed, so the CI build never needs Pillow. Re-run
with:

    uv run python build_tools/make_icons.py

`emoji_tv.png` is U+1F4FA from Google's Noto Emoji (Apache License 2.0),
https://github.com/googlefonts/noto-emoji/blob/main/2D/png/512/emoji_u1f4fa.png.
Pillow cannot draw the COLRv1 colour font, hence the committed PNG.
"""

import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
EMOJI = os.path.join(HERE, 'emoji_tv.png')
STATIC_ICONS = os.path.join('static', 'icons')

# Same red as the site's header and theme colour.
RED = (192, 57, 43, 255)
TRANSPARENT = (0, 0, 0, 0)


def icon(size: int, scale: float, background=RED) -> Image.Image:
	"""The emoji centred on `background`, taking `scale` of the icon's width.

	Maskable icons get a smaller scale: launchers crop them to a circle or a
	squircle, and only the central 80 % is guaranteed to stay visible.
	"""
	emoji = Image.open(EMOJI).convert('RGBA')
	emoji = emoji.crop(emoji.getbbox())
	side = round(size * scale)
	emoji.thumbnail((side, side), Image.LANCZOS)

	image = Image.new('RGBA', (size, size), background)
	offset = ((size - emoji.width) // 2, (size - emoji.height) // 2)
	image.alpha_composite(emoji, offset)
	return image


def main() -> None:
	os.makedirs(STATIC_ICONS, exist_ok=True)

	for size in (192, 512):
		icon(size, 0.7).save(os.path.join(STATIC_ICONS, f'icon-{size}.png'), optimize=True)
		icon(size, 0.56).save(os.path.join(STATIC_ICONS, f'maskable-{size}.png'), optimize=True)

	# iOS rounds the corners itself and wants no transparency.
	apple = icon(180, 0.7).convert('RGB')
	apple.save(os.path.join(STATIC_ICONS, 'apple-touch-icon.png'), optimize=True)

	# Header logo: an image rather than the 📺 character, whose position and
	# look change with every platform's emoji font. 64 px covers 2x screens.
	icon(64, 1.0, TRANSPARENT).save(os.path.join(STATIC_ICONS, 'tv.png'), optimize=True)

	# Browser tabs are tiny: the bare emoji, edge to edge, reads best.
	icon(64, 1.0, TRANSPARENT).save(
		os.path.join('static', 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)]
	)

	print('Icons written to', STATIC_ICONS)


if __name__ == '__main__':
	main()
