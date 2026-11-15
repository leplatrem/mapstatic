import json
from pathlib import Path

import pytest
import typer

from mapstatic.cli import build_directory, build_site, valid_coordinates


def make_feature(map_dir: Path, feature_id: str = "sample-place") -> Path:
    feature_dir = map_dir / feature_id
    feature_dir.mkdir(parents=True)
    feature = {
        "type": "Feature",
        "properties": {"source": "Sample registry"},
        "geometry": {"type": "Point", "coordinates": [2.17, 41.38]},
    }
    (feature_dir / "geometry.geojson").write_text(json.dumps(feature), encoding="utf-8")
    (feature_dir / "page.md").write_text(
        "# Sample Place · local record\n\nA **useful** description.\n\n![View](images/view.jpg)\n",
        encoding="utf-8",
    )
    image_dir = feature_dir / "images"
    image_dir.mkdir()
    (image_dir / "view.jpg").write_bytes(b"image bytes")
    return feature_dir


def test_build_generates_map_detail_markdown_and_image(tmp_path: Path) -> None:
    map_dir = tmp_path / "sample-map"
    feature_dir = make_feature(map_dir)
    output = tmp_path / "site"

    count = build_site(map_dir, output, None, "https://tiles.example/{z}/{x}/{y}.png", "Tiles")

    assert count == 1
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "Sample Map" in index
    assert 'id="map"' in index
    assert 'id="detail-panel"' in index
    data = json.loads((output / "features.geojson").read_text(encoding="utf-8"))
    assert data["features"][0]["id"] == "sample-place"
    assert data["features"][0]["properties"]["title"] == "Sample Place · local record"
    assert data["features"][0]["properties"]["source"] == "Sample registry"
    detail = json.loads((output / "details.json").read_text(encoding="utf-8"))["sample-place"]
    assert '<h2 class="detail-title">Sample Place · local record</h2>' in detail
    assert "Properties" in detail
    assert '<th scope="row">Source</th>' in detail
    assert "<strong>useful</strong>" in detail
    assert "content/sample-place/images/view.jpg" in detail
    assert not (output / "places").exists()
    assert (
        output / "content" / "sample-place" / "images" / "view.jpg"
    ).read_bytes() == b"image bytes"
    config = json.loads((output / "map-config.json").read_text(encoding="utf-8"))
    assert config == {
        "tileUrl": "https://tiles.example/{z}/{x}/{y}.png",
        "tileAttribution": "Tiles",
    }
    style = json.loads((output / "style.json").read_text(encoding="utf-8"))
    assert style["point"]["fillColor"] == "#e45d3f"
    assert style["geometry"]["weight"] == 4
    assert (feature_dir / "geometry.geojson").is_file()
    map_script = (output / "assets" / "map.js").read_text(encoding="utf-8")
    assert "bindTooltip(tooltip" in map_script


def test_build_supports_markdown_feature_with_embedded_geojson(tmp_path: Path) -> None:
    map_dir = tmp_path / "recent-expulsions"
    map_dir.mkdir()
    page = map_dir / "carmen.md"
    page.write_text(
        "# Carmen\n\n```geojson\n"
        '{"type":"Feature","properties":{"source":"Tenant diary"},'
        '"geometry":{"type":"Point","coordinates":[2.1771,41.3849]}}'
        "\n```\n\nA **short account**.\n",
        encoding="utf-8",
    )
    output = tmp_path / "site"

    count = build_site(map_dir, output, None, "tiles", "attribution")

    assert count == 1
    feature = json.loads((output / "features.geojson").read_text(encoding="utf-8"))["features"][0]
    assert feature["id"] == "carmen"
    assert feature["properties"] == {"source": "Tenant diary", "title": "Carmen"}
    detail = json.loads((output / "details.json").read_text(encoding="utf-8"))["carmen"]
    assert "<strong>short account</strong>" in detail
    assert "```geojson" not in detail


@pytest.mark.parametrize(
    ("kind", "coordinates"),
    [
        ("Point", [2.17, 41.38]),
        ("MultiPoint", [[2.17, 41.38], [2.18, 41.39]]),
        ("LineString", [[2.17, 41.38], [2.18, 41.39]]),
        ("MultiLineString", [[[2.17, 41.38], [2.18, 41.39]]]),
        ("Polygon", [[[2.17, 41.38], [2.18, 41.38], [2.18, 41.39], [2.17, 41.38]]]),
        (
            "MultiPolygon",
            [[[[2.17, 41.38], [2.18, 41.38], [2.18, 41.39], [2.17, 41.38]]]],
        ),
    ],
)
def test_build_supports_bare_geojson_geometries(
    tmp_path: Path, kind: str, coordinates: object
) -> None:
    map_dir = tmp_path / "sample-map"
    feature_dir = map_dir / "bare-shape"
    feature_dir.mkdir(parents=True)
    (feature_dir / "geometry.geojson").write_text(
        json.dumps({"type": kind, "coordinates": coordinates}), encoding="utf-8"
    )
    (feature_dir / "page.md").write_text("# Bare Shape\n\nA geometry without properties.\n")
    output = tmp_path / "site"

    build_site(map_dir, output, None, "tiles", "attribution")

    feature = json.loads((output / "features.geojson").read_text(encoding="utf-8"))["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == kind
    assert feature["properties"] == {"title": "Bare Shape"}


def test_build_fails_for_missing_page(tmp_path: Path) -> None:
    map_dir = tmp_path / "broken-map"
    feature_dir = make_feature(map_dir)
    (feature_dir / "page.md").unlink()

    with pytest.raises(typer.BadParameter, match="needs both geometry.geojson and page.md"):
        build_site(map_dir, tmp_path / "site", None, "tiles", "attribution")


def test_build_auto_detects_template_in_map_folder(tmp_path: Path) -> None:
    map_dir = tmp_path / "custom-map"
    make_feature(map_dir)
    (map_dir / "template.html").write_text(
        "<title>{{ title }}</title>{{ head }}<header>Map template</header>"
        "{{ map }}{{ panel }}{{ scripts }}",
        encoding="utf-8",
    )

    build_site(map_dir, tmp_path / "site", None, "tiles", "attribution")

    index = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Map template" in index
    assert "<title>Custom Map</title>" in index


def test_map_style_overrides_defaults(tmp_path: Path) -> None:
    map_dir = tmp_path / "custom-map"
    make_feature(map_dir)
    (map_dir / "style.json").write_text(
        json.dumps({"point": {"fillColor": "#123456"}}), encoding="utf-8"
    )

    build_site(map_dir, tmp_path / "site", None, "tiles", "attribution")

    style = json.loads((tmp_path / "site" / "style.json").read_text(encoding="utf-8"))
    assert style["point"]["fillColor"] == "#123456"
    assert style["point"]["radius"] == 7
    assert style["geometry"]["color"] == "#e45d3f"


def test_build_directory_preserves_site_tree_and_builds_nested_maps(tmp_path: Path) -> None:
    source = tmp_path / "example"
    site_root = source / "map"
    site_root.mkdir(parents=True)
    (site_root / "index.html").write_text(
        '<a href="first-map/index.html">First</a>', encoding="utf-8"
    )
    (site_root / "home.css").write_text("body { color: green; }", encoding="utf-8")
    hidden_assets = site_root / ".well-known"
    hidden_assets.mkdir()
    (hidden_assets / "security.txt").write_text("Contact: hello@example.test", encoding="utf-8")
    (site_root / ".gitignore").write_text("output/", encoding="utf-8")
    first = make_feature(site_root / "first-map", "place-one")
    second = make_feature(site_root / "second-map", "place-two")
    (site_root / "first-map" / "template.html").write_text(
        "{{ title }}{{ head }}{{ map }}{{ panel }}{{ scripts }}",
        encoding="utf-8",
    )
    output = tmp_path / "build"

    feature_count, map_count = build_directory(source, output, None, "tiles", "attribution")

    assert (feature_count, map_count) == (2, 2)
    assert (output / "map" / "index.html").read_text(encoding="utf-8") == (
        '<a href="first-map/index.html">First</a>'
    )
    assert (output / "map" / "home.css").is_file()
    assert (output / "map" / ".well-known" / "security.txt").is_file()
    assert not (output / "map" / ".gitignore").exists()
    assert (output / "map" / "first-map" / "index.html").is_file()
    assert (output / "map" / "second-map" / "details.json").is_file()
    assert not (output / "map" / "first-map" / "place-one").exists()
    assert (first / "geometry.geojson").is_file()
    assert (second / "geometry.geojson").is_file()


def test_build_fails_for_invalid_coordinates(tmp_path: Path) -> None:
    map_dir = tmp_path / "broken-map"
    feature_dir = make_feature(map_dir)
    feature = json.loads((feature_dir / "geometry.geojson").read_text(encoding="utf-8"))
    feature["geometry"]["coordinates"] = [181, 95]
    (feature_dir / "geometry.geojson").write_text(json.dumps(feature), encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="invalid coordinates for Point"):
        build_site(map_dir, tmp_path / "site", None, "tiles", "attribution")


@pytest.mark.parametrize(
    ("kind", "coordinates"),
    [
        ("Point", [0, 0]),
        ("MultiPoint", [[0, 0], [1, 1]]),
        ("LineString", [[0, 0], [1, 1]]),
        ("MultiLineString", [[[0, 0], [1, 1]]]),
        ("Polygon", [[[0, 0], [1, 0], [1, 1], [0, 0]]]),
        ("MultiPolygon", [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]),
    ],
)
def test_valid_coordinates_accepts_supported_geometries(kind: str, coordinates: object) -> None:
    assert valid_coordinates(kind, coordinates)


@pytest.mark.parametrize(
    ("kind", "coordinates"),
    [
        ("Point", [181, 0]),
        ("LineString", [[0, 0]]),
        ("Polygon", [[[0, 0], [1, 0], [1, 1], [2, 2]]]),
        ("MultiPolygon", [[[[0, 0], [1, 0], [1, 1], [0, 0]]], []]),
    ],
)
def test_valid_coordinates_rejects_malformed_geometries(kind: str, coordinates: object) -> None:
    assert not valid_coordinates(kind, coordinates)
