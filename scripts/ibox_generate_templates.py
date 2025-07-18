#!/usr/bin/env python3
import os
import json
import concurrent.futures
from traceback import print_exc
from tqdm import tqdm

from awsibox import override, args, cfg, RP, discover, generate


# to avoid flake8 complain about not used imported override
override.yaml.Dumper

args = args.get_args()


def output_template(template, brand=None, envrole=None):
    if args.Output == "json":
        output = template.to_json()
        extension = ".json"
    elif args.Output == "cjson":
        output = template.to_json(indent=None)
        extension = ".json"
    elif args.Output == "yaml":
        output = template.to_yaml(long_form=True)
        extension = ".yaml"

    if args.action == "view":
        print(output)
    elif args.action == "write":
        file_path = os.path.join(os.getcwd(), "templates", brand)
        try:
            os.makedirs(file_path)
        except Exception:
            pass
        file_name = os.path.join(file_path, envrole + extension)
        with open(file_name, "w") as f:
            f.write(output + "\n")

        return f"Brand: {brand} - EnvRole: {envrole}"


def get_template():
    # save base cfg ..
    cfg_base = cfg.__dict__.copy()

    cfg.BUILD_ENVS = cfg.BuildEnvs({})
    RP.build_RP()

    # ..and common no brand parsed yaml cfg
    cfg_base_yaml_common_no_brand = cfg.YAML_COMMON_NO_BRAND

    try:
        template = generate.generate()
    finally:
        # restore base cfg (every dynamic dict in cfg need to be cleared)
        cfg.OBJS.clear()
        cfg.__dict__.clear()
        cfg.__dict__.update(cfg_base)
        cfg.YAML_COMMON_NO_BRAND = cfg_base_yaml_common_no_brand

    return template


def do_process(stacktype, envrole):
    cfg.envrole = envrole
    cfg.stacktype = stacktype
    template = get_template()
    return output_template(template, cfg.brand, envrole)


def concurrent_exec(roles, kwargs):
    exit_with_error = False
    with concurrent.futures.ProcessPoolExecutor(**kwargs) as executor:
        data = {}
        future_to_role = {}
        for n in roles:
            stacktype = n[0]
            envrole = n[1]
            ex_sub = executor.submit(do_process, stacktype, envrole)
            future_to_role[ex_sub] = envrole

        for future in (
            tqdm(
                concurrent.futures.as_completed(future_to_role),
                total=len(future_to_role),
                desc="Generating templates",
            )
            if len(roles) > 1
            else concurrent.futures.as_completed(future_to_role)
        ):
            role = future_to_role[future]
            try:
                data[role] = future.result()
            except Exception as e:
                tqdm.write(f"{role} generated an exception: {e}")
                print_exc()
                exit_with_error = True
                break
            else:
                tqdm.write(data[role])
        for future in future_to_role:
            future.cancel()

    if exit_with_error:
        exit(1)


# use CloudFormationResourceSpecification.json to generate cfg.CFG_TO_FUNC
def generate_cfg_to_func():
    d = {}
    for n in ["Parameter", "Condition", "Mapping"]:
        d[n] = cfg.CFG_TO_FUNC_OVERRIDE[n]
    for n in cfg.cfm_res_spec["ResourceTypes"]:
        if n.startswith("AWS::"):
            res_arr = n.split("::")
            res_name = n.replace("AWS", "").replace(":", "")
            res_mod = res_arr[1].lower()
            res_func = res_arr[2]
            # names overrides
            if res_mod in cfg.CFG_TO_FUNC_RENAME:
                res_mod = cfg.CFG_TO_FUNC_RENAME[res_mod]
            if res_name in cfg.CFG_TO_FUNC_RENAME:
                res_name = cfg.CFG_TO_FUNC_RENAME[res_name]
            if res_func in cfg.CFG_TO_FUNC_RENAME:
                res_func = cfg.CFG_TO_FUNC_RENAME[res_func]
            #
            d[res_name] = {
                "func": (res_mod, res_func),
            }
            # conf overrides
            if res_name in cfg.CFG_TO_FUNC_OVERRIDE:
                d[res_name].update(cfg.CFG_TO_FUNC_OVERRIDE[res_name])
    for n in [
        "CloudFrontVpcOrigin",
        "CloudFrontLambdaFunctionAssociation",
        "CCRReplicateRegions",
        "Output",
    ]:
        d[n] = cfg.CFG_TO_FUNC_OVERRIDE[n]
    cfg.CFG_TO_FUNC = d


def main():
    # read CloudFormationResourceSpecification to get CloudFormation Resources Properties
    # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-resource-specification.html
    with open(
        os.path.join(cfg.APP_DIR, "aws", "CloudFormationResourceSpecification.json"),
        "r",
    ) as cfm_res_spec_json:
        cfg.cfm_res_spec = json.load(cfm_res_spec_json)

    generate_cfg_to_func()

    if args.action == "view":
        discover_map = discover.discover([args.Brand], [args.EnvRole], [])

        cfg.brand = args.Brand
        try:
            role = discover_map[cfg.brand][0]
        except Exception:
            pass
        else:
            do_process(role[0], role[1])
    elif args.action == "write":
        discover_map = discover.discover(args.Brands, args.EnvRoles, args.StackTypes)

        for brand, roles in discover_map.items():
            cfg.brand = brand
            if args.jobs:
                kwargs = {"max_workers": args.jobs}
            else:
                kwargs = {}
            concurrent_exec(sorted(set(roles)), kwargs)


if __name__ == "__main__":
    main()
