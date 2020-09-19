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


def get_files(brand):
    files = []

    path_int = os.path.join(cfg.PATH_INT, brand)
    path_ext = os.path.join(cfg.PATH_EXT, brand)

    for n in [path_int, path_ext]:
        for root, directories, filenames in os.walk(n, topdown=True):
            try:
                directories.remove('UNUSED')
            except Exception:
                pass
            for filename in filenames:
                if not filename.startswith('.'):
                    files.append(os.path.join(root, filename))

    return files


def build_discover_map(brand, files, stacktypes):
    roles = []

    for n in files:
        try:
            with open(n, 'r', encoding='utf-8') as f:
                s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

                if any(
                        s.find((f'{pattern}{t}').encode('utf-8')) != -1
                        for t in stacktypes):
                    base_name = os.path.basename(n)
                    role = os.path.splitext(base_name)[0]
                    roles.append(role)
        except IOError:
            pass

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
    global pattern
    global ext_brands

    pattern = ' StackType: '

    discover_map = {}

    if brands:
        ext_brands = list(brands)
    else:
        ext_brands = get_brands()
        brands = list(ext_brands)

    brands.append('BASE')

    for brand in brands:
        if envroles:
            files = []
            for role in envroles:
                files.append(
                    os.path.join(cfg.PATH_EXT, brand, role + '.yml'))
                if brand == 'BASE':
                    files.append(
                        os.path.join(cfg.PATH_INT, brand, role + '.yml'))
        else:
            files = get_files(brand)

        build_discover_map(brand, files, stacktypes)

    return discover_map
