"""Tests for simulator adapter registry."""

from autoairac.config import PathsConfig
from autoairac.simulators.registry import all_simulator_ids, create_adapter


def test_all_simulators_registered() -> None:
    ids = all_simulator_ids()
    assert "xplane12" in ids
    assert "msfs2020" in ids


def test_create_xplane_adapter() -> None:
    adapter = create_adapter("xplane12", PathsConfig())
    assert adapter.id == "xplane12"
    patterns = adapter.torrent_file_patterns()
    assert patterns == ("*xplane12_native*",)


def test_xplane_pattern_excludes_aerosoft_pack() -> None:
    from autoairac.download.qbittorrent import QBittorrentDownloader

    patterns = ("*xplane12_native*",)
    assert QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/xplane12_native_2607.zip", patterns
    )
    assert not QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_xp12_2607.zip", patterns
    )