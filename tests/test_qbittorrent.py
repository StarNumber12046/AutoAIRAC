"""Tests for qBittorrent helpers."""

from autoairac.download.qbittorrent import _info_hash_from_url


def test_info_hash_from_magnet() -> None:
    magnet = (
        "magnet:?xt=urn:btih:0D92B3A1A44F4F4DAFC72075CEC9DBC9FCFB8C2E"
        "&tr=http%3A%2F%2Fbt3.t-ru.org%2Fann%3Fmagnet"
    )
    assert _info_hash_from_url(magnet) == "0d92b3a1a44f4f4dafc72075cec9dbc9fcfb8c2e"