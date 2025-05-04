import json
import glob
import logging
import os

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .loaders import basic_loader
from .utils import merge_geometries


logger = logging.getLogger(__name__)


@click.group()
@click.option("--input", "-i", default="contents", help="Path to content files")
@click.option("--templates", "-t", default="templates", help="Path to templates files")
@click.option("--output", "-o", default="html", help="Path to output folder")
@click.pass_context
def cli(ctx, input, templates, output):
    ctx.obj["input_folder"] = input
    ctx.obj["templates_folder"] = templates
    ctx.obj["output_folder"] = output


@cli.command()
@click.pass_context
def build(ctx):
    input_folder = ctx.obj["input_folder"]
    templates_folder = ctx.obj["templates_folder"]
    output_folder = ctx.obj["output_folder"]

    elements_folders = [
        f for f in glob.glob(os.path.join(input_folder, "*"))
        if os.path.isdir(f)
    ]

    elements = []
    for element_folder in elements_folders:
        logger.debug("Process %r", element_folder)
        element = basic_loader(element_folder)
        elements.append(element)

    try:
        os.mkdir(output_folder)
    except FileExistsError:
        pass

    merged_geometries = merge_geometries([
        element.geometry for element in elements
    ])
    output_file = os.path.join(output_folder, "index.geojson")
    logger.info("Write merged geometries file %r", output_file)
    with open(output_file, "w") as f:
        json.dump(f, merged_geometries)

    jinja_env = Environment(
        loader=FileSystemLoader(templates_folder)
    )

    template = jinja_env.get_template("index.html")
    html = template.render(elts=elements)
    output_file = os.path.join(output_folder, f"index.html")
    logger.info("Write HTML file %r", output_file)
    with open(output_file, "w") as f:
        f.write(html)

    for element in elements:
        template = jinja_env.get_template("main.html")
        html = template.render(elt=element)
        output_file = os.path.join(output_folder, f"{element.slug}.html")
        logger.info("Write HTML file %r", output_file)
        with open(output_file, "w") as f:
            f.write(html)


def main():
    logging.basicConfig(level=logging.DEBUG)
    cli(obj={})


if __name__ == "__main__":
    main()
