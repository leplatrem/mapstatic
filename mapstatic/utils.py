def casing(filename):
    words = filename.replace("_", " ").replace("-", " ").split(" ")
    return " ".join(w.title() for w in words)


def merge_geometries(geoms):
    return geoms
