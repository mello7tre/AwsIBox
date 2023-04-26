import sys
import os
import mmap

from . import cfg


def build_discover_map(brand, stacktypes, envroles):
    if not stacktypes and not envroles:
        # include all roles in all stacktypes
        stacktypes = cfg.STACK_TYPES

    roles = []

    path_int = os.path.join(cfg.PATH_INT, brand, cfg.STACKS_DIR)
    path_ext = os.path.join(cfg.PATH_EXT, brand, cfg.STACKS_DIR)

    for n in [path_int, path_ext]:
        for root, directories, filenames in os.walk(n, topdown=True):
            try:
                directories.remove("UNUSED")
            except Exception:
                pass
            for filename in filenames:
                stacktype = os.path.basename(root)
                role = os.path.splitext(os.path.basename(filename))[0]
                if (
                    not filename.startswith(".")
                    and not filename == "i_type.yml"
                    and (stacktype in stacktypes or role in envroles)
                ):
                    roles.append((stacktype, role))

    if brand == cfg.IBOX_BRAND_DIR:
        # add all roles found in ibox conf to all other brands
        for n in ext_brands:
            if n != cfg.IBOX_BRAND_DIR:
                add_to_map(n, roles)
    else:
        # add roles to brand
        add_to_map(brand, roles)


def add_to_map(brand, roles):
    global discover_map

    try:
        discover_map[brand].extend(roles)
    except Exception:
        discover_map[brand] = roles


def discover(brands, envroles, stacktypes):
    global discover_map
    global ext_brands

    discover_map = {}

    if brands:
        ext_brands = list(brands)
    else:
        ext_brands = os.listdir(cfg.PATH_EXT)

    # cycle on external brands + ibox one
    for brand in set(ext_brands + [cfg.IBOX_BRAND_DIR]):
        build_discover_map(brand, stacktypes, envroles)

    return discover_map
