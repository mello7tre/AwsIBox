#!/usr/bin/env python3
import sys
import os
import json

from troposphere import Template
from awsibox import args, cfg, RP, discover, generate

args = args.get_args()


def output_template(template, brand=None, role=None):
    if args.Output == 'json':
        output = template.to_json()
        extension = '.json'
    elif args.Output == 'cjson':
        output = template.to_json(indent=None)
        extension = '.json'
    elif args.Output == 'yaml':
        output = template.to_yaml(long_form=True)
        extension = '.yaml'

    if args.action == 'view':
        print(output)
    elif args.action == 'write':
        file_path = os.path.join(os.getcwd(), 'templates', brand)
        try:
            os.makedirs(file_path)
        except Exception:
            pass
        file_name = os.path.join(file_path, role + extension)
        with open(file_name, 'w') as f:
            f.write(output + '\n')


def get_template():
    # save base cfg
    cfg_base = cfg.__dict__.copy()

    cfg.template = Template()
    RP.build_RP()
    template = generate.generate()

    # restore base cfg
    cfg.__dict__.clear()
    cfg.__dict__.update(cfg_base)

    return template


if args.action == 'view':
    cfg.envrole = args.EnvRole
    cfg.brand = args.Brand

    template = get_template()

    output_template(template)

elif args.action == 'write':
    discover_map = discover.discover(
        args.Brands, args.EnvRoles, args.StackTypes)

    for brand, roles in discover_map.items():
        cfg.brand = brand

        for role in roles:
            cfg.envrole = role

            print('Brand: %s - EnvRole: %s' % (brand, role))

            try:
                template = get_template()
            except Exception as e:
                print('ERROR: %s' % e)
                exit(1)

            output_template(template, brand, role)
