from pprint import pprint, pformat
import argparse

import cfg


# parse main argumets
def get_args():
    parser = argparse.ArgumentParser(description='BUILD STACK JSON')
    parser.add_argument('--EnvRole', help='Stack EnvRole', required=True, type=str)
    parser.add_argument('--Brand', help='Brand', required=True, type=str)
    parser.add_argument('--Debug', help='Show RP Dict', action='store_true')
    args = parser.parse_args()
    return args


args = get_args()

cfg.envrole = args.EnvRole
cfg.brand = args.Brand
cfg.debug = args.Debug
