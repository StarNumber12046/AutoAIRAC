"""Tests for simulator adapter registry."""

from autoairac.config import PathsConfig
from autoairac.simulators.registry import all_simulator_ids, create_adapter


def test_all_simulators_registered() -> None:
    ids = all_simulator_ids()
    assert "xplane12" in ids
    assert "msfs2020" in ids
    assert "p3d4" in ids
    assert "p3d5" in ids


def test_create_xplane_adapter() -> None:
    adapter = create_adapter("xplane12", PathsConfig())
    assert adapter.id == "xplane12"
    patterns = adapter.torrent_file_patterns()
    assert patterns == ("*xplane12_native*",)


def test_create_p3d4_adapter() -> None:
    adapter = create_adapter("p3d4", PathsConfig())
    assert adapter.id == "p3d4"
    assert adapter.display_name == "Prepar3D v4"


def test_p3d4_pattern_matches_v4_archives() -> None:
    from autoairac.download.qbittorrent import QBittorrentDownloader

    patterns = create_adapter("p3d4", PathsConfig()).torrent_file_patterns()
    assert QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_p3dv4_2607.zip", patterns
    )
    assert QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_p3dv45_2607.zip", patterns
    )


def test_p3d5_pattern_matches_v45_combined_pack() -> None:
    from autoairac.download.qbittorrent import QBittorrentDownloader

    patterns = create_adapter("p3d5", PathsConfig()).torrent_file_patterns()
    assert QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_p3dv45_2607.zip", patterns
    )
    assert not QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_p3dv4_2607.zip", patterns
    )


def test_xplane_pattern_excludes_aerosoft_pack() -> None:
    from autoairac.download.qbittorrent import QBittorrentDownloader

    patterns = ("*xplane12_native*",)
    assert QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/xplane12_native_2607.zip", patterns
    )
    assert not QBittorrentDownloader._matches_any(
        "Navigraph AIRAC 2607/as_xp12_2607.zip", patterns
    )