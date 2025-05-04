import json
import os
import pathlib

import markdown

from .models import Element


def casing(filename):
    words = filename.replace("_", " ").replace("-", " ").split(" ")
    return " ".join(w.title() for w in words)


def basic_loader(folder):
    md = markdown.Markdown(extensions=["meta"])

    slug = os.path.basename(folder)

    geometry_doc = pathlib.Path(folder, "main.geojson")
    geometries = json.loads(geometry_doc.read_text(encoding="utf-8"))

    main_doc = pathlib.Path(folder, "main.md")
    data = main_doc.read_text(encoding="utf-8")

    content = md.reset().convert(data)
    flatten = {k: v[0] for k, v in md.Meta.items()}
    md.reset()

    return Element.parse_obj(
        {
            "slug": slug,
            "title": casing(slug),
            "description": content,
            "geometries": geometries,
            **flatten,
        }
    )
