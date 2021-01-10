from pprint import pprint, pformat
import argparse

from . import cfg


# parse main argumets
def get_args():
    parser = argparse.ArgumentParser(
        description='Generate AWS CloudFormation Stack Templates')

    # subparser
    subparsers = parser.add_subparsers(help='Desired Action',
                                       required=True, dest='action')

    # parent parser args
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-R', '--Regions', help='Regions to enable',
                               nargs='+', default=cfg.DEFAULT_REGIONS)
    parent_parser.add_argument('-o', '--Output', help='Output Format',
                               choices=['json', 'cjson', 'yaml'],
                               default='yaml')

    # view parser
    parser_view = subparsers.add_parser(
        'view', parents=[parent_parser],
        help='Generate template and print to standard output')
    parser_view.add_argument('-r', '--EnvRole', help='Stack EnvRole',
                             required=True, type=str)
    parser_view.add_argument('-b', '--Brand', help='Brand',
                             required=True, type=str)
    parser_view.add_argument('-d', '--Debug', help='Show RP Dict',
                             action='store_true')

    # write parser
    parser_write = subparsers.add_parser(
        'write', parents=[parent_parser],
        help=('Generate template '
              'and write to "template/${brand}/$envrole" file'))

    parser_write.add_argument(
        '-b', '--Brands',
        help='Limit generation to EnvRoles defined in the specified Brands',
        nargs='+')
    parser_write.add_argument(
        '-j', '--jobs',
        help='Max concurrent template generation jobs', type=int)

    parser_write.add_argument(
        '-r', '--EnvRoles',
        help='Limit generation to specified EnvRoles',
        nargs='+', default=[])

    parser_write.add_argument(
        '-t', '--StackTypes',
        help='Limit generation to EnvRoles of the specified StackTypes',
        nargs='+', default=[])

    args = parser.parse_args()

    try:
        cfg.debug = args.Debug
    except Exception:
        cfg.debug = None
    cfg.regions = args.Regions

    return args
