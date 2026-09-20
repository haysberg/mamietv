from utils.images import _filename, _small_variant

ICON = (
	'https://www.programme-tv.net/imgre/fit/~2~channel~f2b6de26acc4dc3e.png'
	'/480x480/quality/100/tf1.png'
)


def test_small_variant_rewrites_the_size_segment():
	assert _small_variant(ICON) == (
		'https://www.programme-tv.net/imgre/fit/~2~channel~f2b6de26acc4dc3e.png'
		'/96x96/quality/80/tf1.png'
	)


def test_small_variant_leaves_other_urls_untouched():
	url = 'https://img.example.org/logo.png'
	assert _small_variant(url) == url


def test_filename_is_a_safe_slug_with_the_right_extension():
	assert _filename('TF1.fr', ICON) == 'TF1_fr.png'
	assert _filename('6ter.fr', ICON) == '6ter_fr.png'
	assert _filename('France 2', 'https://x/logo.JPEG') == 'France_2.jpg'
	assert _filename('M6', 'https://x/logo') == 'M6.png'
