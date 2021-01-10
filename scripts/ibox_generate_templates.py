#!/usr/bin/env python3
import sys
import os
import json
import concurrent.futures
from traceback import print_exc

from troposphere import Template
from awsibox import args, cfg, RP, discover, generate

args = args.get_args()


def output_template(template, brand=None, envrole=None):
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
        file_name = os.path.join(file_path, envrole + extension)
        with open(file_name, 'w') as f:
            f.write(output + '\n')

        print(f'Brand: {brand} - EnvRole: {envrole}')


def get_template():
    # save base cfg
    cfg_base = cfg.__dict__.copy()

    cfg.template = Template()
    RP.build_RP()

    try:
        template = generate.generate()
    finally:
        # restore base cfg
        cfg.__dict__.clear()
        cfg.__dict__.update(cfg_base)

    return template


def do_process(stacktype, envrole):
    cfg.envrole = envrole
    cfg.stacktype = stacktype
    template = get_template()
    output_template(template, cfg.brand, envrole)


def concurrent_exec(roles, kwargs):
    with concurrent.futures.ProcessPoolExecutor(**kwargs) as executor:
        data = {}
        future_to_role = {}
        for n in roles:
            stacktype = n[0]
            envrole = n[1]
            ex_sub = executor.submit(do_process, stacktype, envrole)
            future_to_role[ex_sub] = envrole

        for future in concurrent.futures.as_completed(future_to_role):
            role = future_to_role[future]
            try:
                data[role] = future.result()
            except Exception as e:
                print(f'{role} generated an exception: {e}')
                print_exc()
                break
        for future in future_to_role:
            future.cancel()


if args.action == 'view':
    discover_map = discover.discover(
        [args.Brand], [args.EnvRole], [])

    cfg.brand = args.Brand
    try:
        role = discover_map[cfg.brand][0]
    except Exception:
        pass
    else:
        do_process(role[0], role[1])
elif args.action == 'write':
    discover_map = discover.discover(
        args.Brands, args.EnvRoles, args.StackTypes)

    for brand, roles in discover_map.items():
        cfg.brand = brand
        if args.jobs:
            kwargs = {'max_workers': args.jobs}
        else:
            kwargs = {}
        concurrent_exec(set(roles), kwargs)
