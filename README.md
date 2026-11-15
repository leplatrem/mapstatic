# Mapstatic

*Mapstatic* builds static, mobile-first interactive maps from GeoJSON and Markdown files. The generated files can be hosted on GitHub Pages or any static file host; no application server is required.

## Features

- Each geometry opens its Markdown details in a side panel.
- Feature titles come from the first Markdown heading and appear on hover.
- Feature properties are shown in the details panel.
- Optional images can be included with Markdown.
- Map appearance can be customized per map with `style.json`.
- Each map can use a custom `template.html`.
- OpenStreetMap tiles are used by default.

## Install

Install the CLI with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install .
```

For development:

```sh
uv sync --extra dev
```

## Map input

A map folder contains map elements as folders or Markdown files, plus optional top-level content:

```text
my-map/
├── template.html       # optional custom page shell
├── style.json          # optional Leaflet styles
├── old-town/
│   ├── geometry.geojson
│   ├── page.md
│   └── images/
│       └── square.jpg
└── river-walk.md
```

### Elements as folder

Each map element folder contains one `geometry.geojson` and one `page.md`. The GeoJSON can be a bare geometry or a GeoJSON Feature (geometry + properties).

```json
{
  "type": "Feature",
  "properties": { "source": "Community walking survey" },
  "geometry": {
    "type": "Point",
    "coordinates": [2.1734, 41.3851]
  }
}
```

```md
# Old Town Square

![The square at sunset](images/square.jpg)

A short description of this place.
```

### Elements as file

A map element can instead be stored in one top-level Markdown file. It should include exactly one fenced `geojson` block containing a bare geometry or a Feature:

````md
# Riverside Steps

```geojson
{
  "type": "LineString",
  "coordinates": [[2.17, 41.38], [2.18, 41.39]]
}
```

The rest of the description for this element.
````

> [!NOTE]
> `GeometryCollection` is not supported.


## Build and preview

```sh
mapstatic build my-map/ --destination site/
python -m http.server --directory site/ 8000
```

Open <http://127.0.0.1:8000>

### Build a site containing multiple maps

Give `mapstatic build` a directory containing a site tree. Files outside detected map folders are copied with their relative paths; detected map folders are replaced with generated map output:

```text
neighborhood/
├── index.html
├── home.css
├── empty-buildings/
│   ├── template.html
│   ├── style.json
│   └── ... feature folders ...
└── recent-expulsions/
    ├── template.html
    ├── style.json
    └── ... feature folders and Markdown files ...
```

## Customize a map

### Appearance

Put `style.json` in a map folder. Its `point` options are passed to Leaflet's `CircleMarker`; `geometry` options are passed to Leaflet paths. Missing options inherit the built-in defaults in `src/mapstatic/static/style.json`.

```json
{
  "point": {
    "radius": 7,
    "color": "#fff",
    "weight": 2,
    "fillColor": "#c24c3d",
    "fillOpacity": 1
  },
  "geometry": {
    "color": "#c24c3d",
    "weight": 4,
    "opacity": 0.9,
    "fillColor": "#c24c3d",
    "fillOpacity": 0.12
  }
}
```

### Page shell

Put `template.html` in the map folder to replace the built-in shell. It must include the `{{ title }}`, `{{ count }}`, `{{ head }}`, `{{ map }}`, `{{ panel }}`, and `{{ scripts }}` slots. Mapstatic uses the template in the map folder automatically. Pass `--template path/to/other.html` to override it for a one-off build.

## Community workflow

Contributors can create or edit map content through GitHub and open a pull request. A successful build checks geometries and required Markdown pages.

## Tiles and attribution

The default basemap uses OpenStreetMap's standard tile service and displays its attribution. Tile services have their own usage policies and capacity limits; for a public or high-traffic deployment, configure a tile provider appropriate for that use. Set `--tile-url` and `--tile-attribution` to use another XYZ tile service.

## Development

```sh
uv sync --extra dev
uv run mapstatic --help
uv run ruff check .
uv run pytest
npm ci
npm run format:check
```

## License

CC0 1.0 Universal
