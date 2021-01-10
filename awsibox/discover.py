import sys
import os
import mmap

from . import cfg


def get_brands():
    brand_int = os.listdir(cfg.PATH_INT)
    brand_ext = os.listdir(cfg.PATH_EXT)

    brands = set(brand_int + brand_ext)

    brands.remove('BASE')

    return brands


def build_discover_map(brand, stacktypes, envroles):
    if not stacktypes and not envroles:
        # include all roles in all stacktypes
        stacktypes = cfg.STACK_TYPES

    roles = []

    path_int = os.path.join(cfg.PATH_INT, brand)
    path_ext = os.path.join(cfg.PATH_EXT, brand)

    for n in [path_int, path_ext]:
        for root, directories, filenames in os.walk(n, topdown=True):
            try:
                directories.remove('UNUSED')
            except Exception:
                pass
            for filename in filenames:
                root_dir = os.path.basename(root)
                stacktype = root_dir.lower()
                role = os.path.splitext(os.path.basename(filename))[0]
                if (root_dir.isupper()
                        and not filename.startswith('.')
                        and not filename == 'TYPE.yml'
                        and (stacktype in stacktypes
                             or role in envroles)):
                    roles.append((stacktype, role))

    if brand == 'BASE':
        for n in ext_brands:
            add_to_map(n, roles)
    else:
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
        ext_brands = get_brands()
        brands = list(ext_brands)

    brands.append('BASE')

    for brand in brands:
        build_discover_map(brand, stacktypes, envroles)

    return discover_map
