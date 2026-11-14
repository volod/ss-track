"""Exact metadata joins: a near name, a query and a secret are not evidence."""

from pathlib import Path

from ss_track.corpus.sources.metadata_join import join_metadata


def test_join_uses_only_an_exact_path_or_source_reference(tmp_path: Path) -> None:
    videos = {
        "videos/no_drone_footage/birds_only/rgb/1.mp4": None,
        "videos/bird.mkv": "https://example.com/bird",
    }
    files = {
        "metadata/videos.csv": "name,license\nno_drone/birds_only/rgb/1,fuzzy-license\nvideos/bird.mkv,\n",
        "metadata/sources.txt": (
            "https://example.com/bird - cc-1.0\n"
            "https://example.com/clip?page=1 - mit\n"
            "personal recordings\n"
        ),
        "metadata/scenarios.yaml": "vocabulary:\n- birds\n",
    }
    stored = []
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="ascii")
        stored.append((name, path, "a" * 64))
    evidence, unresolved = join_metadata(videos, tuple(stored))

    near = evidence.get("videos/no_drone_footage/birds_only/rgb/1.mp4", None)
    assert near is None or near.license_name is None
    assert evidence["videos/bird.mkv"].license_name == "cc-1.0"
    assert evidence["videos/bird.mkv"].association == "matched"
    text = " ".join(item.detail for item in unresolved)
    assert "fuzzy-license" not in text
    assert "page=1" not in text
    assert "personal recordings" in text
    assert any(item.path == "metadata/scenarios.yaml" for item in unresolved)


def test_a_repeated_yaml_key_is_not_applied(tmp_path: Path) -> None:
    path = tmp_path / "clip.yaml"
    path.write_text("path: videos/clip.mkv\nlicense: mit\nlicense: cc-1.0\n", encoding="ascii")
    evidence, unresolved = join_metadata(
        {"videos/clip.mkv": None}, (("clip.yaml", path, "b" * 64),)
    )
    assert evidence == {}
    assert unresolved[0].detail.endswith("could not be read")


def _stored(tmp_path: Path, files: dict[str, str]) -> tuple[tuple[str, Path, str], ...]:
    stored = []
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="ascii")
        stored.append((name, path, "c" * 64))
    return tuple(stored)


def test_a_name_rule_joins_a_prefixed_csv_row_to_its_video(tmp_path: Path) -> None:
    videos: dict[str, str | None] = {
        "videos/no_drone_footage/birds_only/rgb/1.mp4": None,
        "videos/drone_footage/rgb/1.mp4": None,
    }
    files = _stored(
        tmp_path,
        {
            "metadata/videos_no_drone.csv": (
                "name,license\n\n\nno_drone/birds_only/rgb/1,cc-1.0\nno_drone/birds_only/rgb/9,mit\n"
            ),
            "metadata/videos_drone.csv": "name,license\nrgb/1,mit\n",
        },
    )
    rules = {
        "metadata/videos_no_drone.csv": ("no_drone/", "videos/no_drone_footage/"),
        "metadata/videos_drone.csv": ("", "videos/drone_footage/"),
    }
    evidence, unresolved = join_metadata(videos, files, rules)

    bird = evidence["videos/no_drone_footage/birds_only/rgb/1.mp4"]
    assert (bird.license_name, bird.association) == ("cc-1.0", "matched")
    assert bird.license_reference == "metadata/videos_no_drone.csv"
    assert evidence["videos/drone_footage/rgb/1.mp4"].license_name == "mit"
    details = [item.detail for item in unresolved]
    assert details == ["metadata/videos_no_drone.csv row 4 matched no video"]


def test_a_name_rule_applies_only_to_its_file(tmp_path: Path) -> None:
    videos: dict[str, str | None] = {"videos/no_drone_footage/birds_only/rgb/1.mp4": None}
    files = _stored(
        tmp_path, {"metadata/other.csv": "name,license\nno_drone/birds_only/rgb/1,mit\n"}
    )
    rules = {"metadata/videos_no_drone.csv": ("no_drone/", "videos/no_drone_footage/")}
    evidence, unresolved = join_metadata(videos, files, rules)
    assert evidence == {}
    assert [item.kind for item in unresolved] == ["unmatched_metadata"]
