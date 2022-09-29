# Mapstatic

*Mapstatic* creates interactive and printable maps from a folder of Markdown files and geographic data.

Each element of the map is materialized by a subfolder that contains a GPX/KML/GeoJSON file, a Markdown document, and some pictures.

## Goals

(Eventually) *mapstatic* would be able to create an interactive Web map showing all elements together. Each element has a dedicated page, with the focused map and the text coming from the structured Markdown content.

- Publish a map within seconds. *mapstatic* can run as a Github action on a repository of files.
- Host a map application without any GIS stack. *mapstatic* builds static content from static files;
- Focus on aesthetics. *mapstatic* creates beautiful static pages for each map, easily printable;
- Focus on minimalism. *mapstatic* uses the minimum amount of JavaScript;

(Eventually) *mapstatic* would output:

- Interactive maps
- Static vectorial maps with legends
- Downloadable / printable pages
- Thumbnails of images
- Converted formats (from/to GPX, KML, GeoJSON)

(Eventually) *mapstatic* would take care of:

- Extracting basic geographical data (length, etc.)
- Replacing keywords or placeholders by icons or widgets
- Obtaining elevation data (eg. using external APIs)
- Linking different elements by proximity or metadata
- Only rebuilding what changed

## Usage

```
$ pip install mapstatic
```

### Add a new element

1. Create a folder, its name will be the map object identifier
1. Store the `main.gpx` (or `.kml`, or `.geojson`) into it
1. Run `mapstatic init my-folder/`
   This will create the Markdown file `main.md`, with a skeleton of one section for each geometry found in the geographical data.
1. Edit the content!

```md
# main.md ; generated-by-version: 0.1

# geometry-1: Via Ferrata Teletubbies (K2)

![Top view](panorama.jpg)

## Description

Along the Congost del MontRebei...

## Attributes

Difficulty: Easy
Trail Type: Loop

# waypoint-1: Ermita de la Pertusa

![Ermita, west side](ermita.jpg)

# waypoint-2:
# waypoint-3:
# waypoint-4:

```

### Build

Once the content of every section looks good enough, generate the contents:

```
$ mapstatic build contents/ --destination=output/
```

## Inspiration

- Static generators like [Pelican](https://getpelican.com) or [Sigal](https://github.com/saimn/sigal)
- [printmaps](https://www.printmaps.net/creating-maps-for-tourist-guides/)
- [Geotrek](https://rando.ecrins-parcnational.fr/en/trek/903316-Eychauda-Lake)

## Technologies

- Python
- Shapely (?)
- Leaflet (?)
- Mapnik (?)
- OpenMapTiles (?)

## License

CC0 1.0 Universal
