from __future__ import annotations

import html
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Annotated

import typer
from markdown_it import MarkdownIt

app = typer.Typer(
    no_args_is_help=True, help="Build interactive map sites from static files."
)
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GEOMETRIES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
GEOJSON_FENCE_RE = re.compile(r"```geojson\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)


def fail(message: str) -> None:
    raise typer.BadParameter(message)


def markdown_html(text: str) -> str:
    return MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True}).render(
        text
    )


def markdown_title_and_body(markdown: str, fallback: str) -> tuple[str, str]:
    parser = MarkdownIt("commonmark", {"html": False})
    tokens = parser.parse(markdown)
    lines = markdown.splitlines()
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag != "h1":
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        parts = getattr(inline, "children", None) or []
        title = "".join(
            part.content for part in parts if part.type in {"text", "code_inline", "image"}
        ).strip()
        if not title and inline is not None:
            title = inline.content.strip()
        if token.map:
            del lines[token.map[0] : token.map[1]]
        return title or fallback, "\n".join(lines)
    return fallback, markdown


def build_site(
    source: Path,
    destination: Path,
    template_path: Path | None,
    tile_url: str,
    tile_attribution: str,
) -> int:
    source = source.resolve()
    if not source.is_dir():
        fail(f"Map folder does not exist: {source}")
    feature_folders = [
        folder
        for folder in sorted(source.iterdir())
        if folder.is_dir() and not folder.name.startswith(".")
    ]
    markdown_features = [
        page for page in sorted(source.glob("*.md")) if page.is_file() and page.name != "README.md"
    ]
    features = []
    output = destination.resolve()
    output.mkdir(parents=True, exist_ok=True)
    asset_dir = output / "assets"
    asset_dir.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).parent / "static" / "style.css", asset_dir / "style.css")
    shutil.copyfile(Path(__file__).parent / "static" / "map.js", asset_dir / "map.js")
    details = {}

    feature_sources = [
        (folder.name, folder, folder / "geometry.geojson", folder / "page.md")
        for folder in feature_folders
    ]
    feature_sources.extend((page.stem, page.parent, page, page) for page in markdown_features)
    source_ids = [feature[0] for feature in feature_sources]
    if len(source_ids) != len(set(source_ids)):
        fail("Feature IDs must be unique across feature folders and Markdown files")
    for feature_id, asset_root, geo_path, md_path in feature_sources:
        if not ID_RE.fullmatch(feature_id):
            fail(
                f"Invalid feature folder '{feature_id}': use lowercase letters, "
                "numbers, and hyphens"
            )
        if not geo_path.is_file() or not md_path.is_file():
            fail(f"Feature '{feature_id}' needs both geometry.geojson and page.md")
        try:
            geojson_text = geo_path.read_text(encoding="utf-8")
            if geo_path == md_path:
                matches = GEOJSON_FENCE_RE.findall(geojson_text)
                if len(matches) != 1:
                    fail(
                        f"Feature '{feature_id}' Markdown must contain exactly one "
                        "```geojson block"
                    )
                geojson_text = matches[0]
            item = json.loads(geojson_text)
        except (json.JSONDecodeError, OSError) as exc:
            fail(f"Feature '{feature_id}' has invalid GeoJSON: {exc}")
        if not isinstance(item, dict):
            fail(f"Feature '{feature_id}' GeoJSON must be an object")
        if item.get("type") in GEOMETRIES:
            item = {"type": "Feature", "properties": {}, "geometry": item}
        elif item.get("type") != "Feature" or not isinstance(item.get("geometry"), dict):
            fail(
                f"Feature '{feature_id}' GeoJSON must be a Geometry or a GeoJSON Feature"
            )
        geometry = item["geometry"]
        geometry_type = geometry.get("type")
        if geometry_type not in GEOMETRIES:
            fail(f"Feature '{feature_id}' has an unsupported or missing geometry type")
        if not valid_coordinates(geometry_type, geometry.get("coordinates")):
            fail(f"Feature '{feature_id}' has invalid coordinates for {geometry_type}")
        properties = item.get("properties") or {}
        if not isinstance(properties, dict):
            fail(f"Feature '{feature_id}' properties must be a JSON object")
        page_markdown = md_path.read_text(encoding="utf-8")
        if geo_path == md_path:
            page_markdown = GEOJSON_FENCE_RE.sub("", page_markdown, count=1)
        title, page_body = markdown_title_and_body(
            page_markdown, feature_id.replace("-", " ").title()
        )
        item["id"] = feature_id
        item["properties"] = {**properties, "title": title}
        features.append(item)

        body = markdown_html(page_body)
        for image in (asset_root / "images").rglob("*") if (asset_root / "images").exists() else []:
            if image.is_file():
                relative = image.relative_to(asset_root)
                target = output / "content" / feature_id / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(image, target)
        body = body.replace('src="images/', 'src="content/' + feature_id + "/images/")
        visible_properties = {
            key: value for key, value in properties.items() if key not in {"title", "url"}
        }
        details[feature_id] = detail_content(title, body, visible_properties)

    if not features:
        fail(f"No feature folders found directly inside {source}")
    (output / "features.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    (output / "details.json").write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (output / "map-config.json").write_text(
        json.dumps({"tileUrl": tile_url, "tileAttribution": tile_attribution}), encoding="utf-8"
    )
    style_path = source / "style.json"
    default_style_path = Path(__file__).parent / "static" / "style.json"
    defaults = json.loads(default_style_path.read_text(encoding="utf-8"))
    if style_path.is_file():
        try:
            style = json.loads(style_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            fail(f"Invalid style.json: {exc}")
        if not isinstance(style, dict) or any(
            key in style and not isinstance(style[key], dict) for key in ("point", "geometry")
        ):
            fail("style.json must be an object with optional 'point' and 'geometry' objects")
    else:
        style = {}
    style = {
        section: {**defaults[section], **style.get(section, {})}
        for section in ("point", "geometry")
    }
    (output / "style.json").write_text(json.dumps(style), encoding="utf-8")
    title = source.name.replace("-", " ").title()
    default_template = Path(__file__).parent / "static" / "template.html"
    detected_template = source / "template.html"
    shell_path = template_path or (
        detected_template if detected_template.is_file() else default_template
    )
    shell = shell_path.read_text(encoding="utf-8")
    required = ("{{ title }}", "{{ head }}", "{{ map }}", "{{ panel }}", "{{ scripts }}")
    missing = [slot for slot in required if slot not in shell]
    if missing:
        fail("HTML template is missing required slots: " + ", ".join(missing))
    html = shell.replace("{{ title }}", html_escape(title)).replace(
        "{{ count }}", str(len(features))
    )
    html = html.replace(
        "{{ head }}",
        '<link rel="stylesheet" href="assets/style.css">'
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@2.0.0-beta.4/dist/leaflet.css">'
        '<script type="importmap">'
        '{"imports":{"leaflet":"https://cdn.jsdelivr.net/npm/leaflet@2.0.0-beta.4/dist/leaflet.js"}}'
        "</script>",
    )
    html = html.replace("{{ map }}", '<div id="map" aria-label="Interactive map"></div>')
    html = html.replace(
        "{{ panel }}",
        '<aside id="detail-panel" class="detail-panel" aria-label="Feature details" '
        'aria-hidden="true" hidden><header class="panel-header">'
        '<span class="panel-label">Details</span>'
        '<button id="close-panel" class="panel-close" type="button" aria-label="Close details">'
        '<span aria-hidden="true">×</span></button></header>'
        '<div id="detail-content" class="detail-content"></div></aside>',
    )
    html = html.replace("{{ scripts }}", '<script type="module" src="assets/map.js"></script>')
    (output / "index.html").write_text(html, encoding="utf-8")
    return len(features)


def is_map_source(folder: Path) -> bool:
    """A map has feature folders directly inside it."""
    if not folder.is_dir():
        return False
    has_markdown_features = any(
        page.is_file() for page in folder.glob("*.md") if page.name != "README.md"
    )
    if has_markdown_features:
        contains_nested_map = any(
            child.is_dir()
            and any(
                grandchild.is_dir()
                and (
                    (grandchild / "geometry.geojson").exists()
                    or (grandchild / "page.md").exists()
                )
                for grandchild in child.iterdir()
            )
            for child in folder.iterdir()
        )
        if not contains_nested_map:
            return True
    for child in folder.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "geometry.geojson").exists() or (child / "page.md").exists():
            return True
    return False


def build_directory(
    source: Path,
    destination: Path,
    template_path: Path | None,
    tile_url: str,
    tile_attribution: str,
) -> tuple[int, int]:
    """Build one map, or copy a site shell and build every map below it."""
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        fail(f"Input directory does not exist: {source}")
    if is_map_source(source):
        return (
            build_site(source, destination, template_path, tile_url, tile_attribution),
            1,
        )

    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    map_sources: list[Path] = []
    for current, directories, _files in os.walk(source):
        current_path = Path(current).resolve()
        directories[:] = [
            directory
            for directory in directories
            if directory not in ignored_dirs and (current_path / directory).resolve() != destination
        ]
        if is_map_source(current_path):
            map_sources.append(current_path)
            directories[:] = []

    if not map_sources:
        fail(f"No map folders found in {source}")

    destination.mkdir(parents=True, exist_ok=True)
    map_sources = sorted(map_sources)
    for current, directories, files in os.walk(source):
        current_path = Path(current).resolve()
        if current_path == destination or destination in current_path.parents:
            directories[:] = []
            continue
        if any(
            map_path == current_path or map_path in current_path.parents for map_path in map_sources
        ):
            directories[:] = []
            continue
        directories[:] = [
            directory
            for directory in directories
            if directory not in ignored_dirs
            and (current_path / directory).resolve() != destination
            and not any(
                map_path == (current_path / directory).resolve() for map_path in map_sources
            )
        ]
        relative = current_path.relative_to(source)
        target_dir = destination / relative
        for filename in files:
            if filename in {".DS_Store", ".gitignore"}:
                continue
            source_file = current_path / filename
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target_dir / filename)

    total_features = 0
    for map_source in map_sources:
        relative = map_source.relative_to(source)
        total_features += build_site(
            map_source,
            destination / relative,
            template_path,
            tile_url,
            tile_attribution,
        )
    return total_features, len(map_sources)


def detail_content(title: str, body: str, properties: dict[str, object]) -> str:
    safe_title = html_escape(title)
    rows = "".join(
        '<tr><th scope="row">'
        + html_escape(str(key).replace("_", " ").replace("-", " ").title())
        + "</th><td>"
        + html_escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
        + "</td></tr>"
        for key, value in properties.items()
    )
    property_table = (
        '<section class="property-card" aria-labelledby="properties-heading">'
        '<h2 id="properties-heading">Properties</h2>'
        '<table class="property-table"><tbody>' + rows + "</tbody></table></section>"
        if rows
        else ""
    )
    return (
        f'<article class="detail-content-inner"><h2 class="detail-title">{safe_title}</h2>'
        f'{property_table}<div class="detail-copy">{body}</div></article>'
    )


def html_escape(value: str) -> str:
    return html.escape(value, quote=True)


def valid_coordinates(kind: str, coordinates: object) -> bool:
    """Check coordinate nesting and minimum positions for the supported GeoJSON types."""
    depth = {
        "Point": 0,
        "MultiPoint": 1,
        "LineString": 1,
        "MultiLineString": 2,
        "Polygon": 2,
        "MultiPolygon": 3,
    }[kind]

    def positions(value: object, remaining: int) -> bool:
        if remaining == 0:
            return (
                isinstance(value, list)
                and len(value) >= 2
                and all(
                    isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
                    for n in value[:2]
                )
                and -180 <= value[0] <= 180
                and -90 <= value[1] <= 90
            )
        return (
            isinstance(value, list)
            and len(value) > 0
            and all(positions(child, remaining - 1) for child in value)
        )

    if not positions(coordinates, depth):
        return False
    if kind == "LineString":
        return len(coordinates) >= 2
    if kind == "MultiLineString":
        return all(len(line) >= 2 for line in coordinates)
    if kind == "Polygon":
        return all(len(ring) >= 4 and ring[0] == ring[-1] for ring in coordinates)
    if kind == "MultiPolygon":
        return all(
            len(ring) >= 4 and ring[0] == ring[-1] for polygon in coordinates for ring in polygon
        )
    return True


@app.command()
def build(
    source: Annotated[Path, typer.Argument(help="Map folder or directory containing maps")],
    destination: Annotated[
        Path, typer.Option("--destination", "-d", help="Output directory")
    ] = Path("site"),
    template: Annotated[
        Path | None,
        typer.Option(
            "--template",
            help="HTML shell slots: {{ map }}, {{ head }}, {{ scripts }}, {{ title }}",
        ),
    ] = None,
    tile_url: Annotated[str, typer.Option("--tile-url", help="XYZ tile URL template")] = TILE_URL,
    tile_attribution: Annotated[
        str, typer.Option("--tile-attribution", help="Attribution HTML for the tile provider")
    ] = TILE_ATTRIBUTION,
) -> None:
    """Build a map or a directory of maps into a static site tree."""
    feature_count, map_count = build_directory(
        source, destination, template, tile_url, tile_attribution
    )
    if map_count == 1:
        typer.echo(f"Built {feature_count} features into {destination}")
    else:
        typer.echo(f"Built {feature_count} features across {map_count} maps into {destination}")


@app.command()
def init(destination: Annotated[Path, typer.Argument(help="New map folder")]) -> None:
    """Create a starter map with one example feature."""
    feature = destination / "example-place"
    feature.mkdir(parents=True, exist_ok=True)
    (feature / "geometry.geojson").write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"source": "Add a source or reference"},
                "geometry": {"type": "Point", "coordinates": [2.1734, 41.3851]},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature / "page.md").write_text(
        "# Example place\n\nDescribe this place in Markdown. "
        "Add images in `images/`, then reference them as `![Caption](images/photo.jpg)`.\n",
        encoding="utf-8",
    )
    typer.echo(f"Created starter map in {destination}")


if __name__ == "__main__":
    app()
