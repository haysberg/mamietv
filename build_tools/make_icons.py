"""Generate the PWA / favicon icons.

Dev-only tool (Pillow lives in the `dev` dependency group). The generated PNGs
and `favicon.ico` are committed, so neither the Docker image nor the CI build
needs Pillow. Re-run with:

    uv run python build_tools/make_icons.py
"""

import os

from PIL import Image, ImageDraw

STATIC_ICONS = os.path.join('static', 'icons')

# Same palette as the site.
RED = (192, 57, 43, 255)
WHITE = (255, 255, 255, 255)

# Supersampling factor: draw big, downscale once, get smooth edges for free.
SS = 4


def _draw_tv(draw: ImageDraw.ImageDraw, size: int, scale: float) -> None:
	"""Draw a simple TV with a play triangle.

	Coordinates are normalized to [0, 1]; `scale` shrinks the whole drawing
	towards the centre, which is what a maskable icon needs (its content must
	stay inside the safe zone).
	"""

	def x(value: float) -> float:
		return (0.5 + (value - 0.5) * scale) * size

	def y(value: float) -> float:
		return (0.5 + (value - 0.5) * scale) * size

	def radius(r: float) -> int:
		return int(r * scale * size)

	# Antennae first, so the screen body hides where they attach.
	draw.line([(x(0.40), y(0.27)), (x(0.29), y(0.15))], fill=WHITE, width=radius(0.03))
	draw.line([(x(0.60), y(0.27)), (x(0.71), y(0.15))], fill=WHITE, width=radius(0.03))
	# Screen body, its red inner, the play triangle and the stand.
	draw.rounded_rectangle([x(0.14), y(0.26), x(0.86), y(0.72)], radius=radius(0.07), fill=WHITE)
	draw.rounded_rectangle([x(0.185), y(0.305), x(0.815), y(0.675)], radius=radius(0.05), fill=RED)
	draw.polygon([(x(0.43), y(0.36)), (x(0.43), y(0.62)), (x(0.66), y(0.49))], fill=WHITE)
	draw.rounded_rectangle([x(0.40), y(0.72), x(0.60), y(0.79)], radius=radius(0.02), fill=WHITE)


def icon(size: int, scale: float = 1.0) -> Image.Image:
	big = size * SS
	image = Image.new('RGBA', (big, big), RED)
	_draw_tv(ImageDraw.Draw(image), big, scale)
	return image.resize((size, size), Image.LANCZOS)


def main() -> None:
	os.makedirs(STATIC_ICONS, exist_ok=True)

	for size in (192, 512):
		icon(size).save(os.path.join(STATIC_ICONS, f'icon-{size}.png'), optimize=True)
		icon(size, scale=0.72).save(
			os.path.join(STATIC_ICONS, f'maskable-{size}.png'), optimize=True
		)

	apple = icon(180).convert('RGB')
	apple.save(os.path.join(STATIC_ICONS, 'apple-touch-icon.png'), optimize=True)

	icon(64).save(os.path.join('static', 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)])

	print('Icons written to', STATIC_ICONS)


if __name__ == '__main__':
	main()
