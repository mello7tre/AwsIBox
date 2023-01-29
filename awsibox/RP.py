import yaml
import yaml.constructor
import sys
import os
import copy
import json
import logging
from pprint import pprint, pformat

from . import cfg


def RP_to_cfg(key, prefix="", overwrite=True, mappedvalues=[]):
    if hasattr(key, "items"):
        for k, v in key.items():
            # remove both * and + that can be present for special IBOX usage
            key_name = f"{prefix}{k}".translate("".maketrans({"*": None, "+": None}))
            try:
                getattr(cfg, key_name)
                exist = True
            except Exception:
                exist = False
            if not exist or overwrite:
                setattr(cfg, key_name, v)
                if key_name not in mappedvalues:
                    cfg.fixedvalues[key_name] = v
            # recursively traverse dict
            # keys name are the concatenation of traversed dict keys
            if isinstance(v, dict):
                for j, w in v.items():
                    RP_to_cfg({f"{k}{j}": w}, prefix, overwrite)


def merge_dict(base, work):
    if isinstance(work, (str, list)) or not base:
        return work
    keys = dict(list(base.items()) + list(work.items())).keys()
    for k in keys:
        if k.endswith("**"):
            # ** is used to replace existing dict instead of merging it
            base[k.replace("**", "")] = work[k]
        elif isinstance(base.get(k), dict) and isinstance(work.get(k), dict):
            base[k] = merge_dict(base[k], work[k])
        elif k.endswith("++") and isinstance(work.get(k), list):
            # ++ is used to append elements to an existing key
            try:
                base[k.replace("++", "")] += work[k]
            except Exception:
                base[k.replace("++", "")] = work[k]
        elif k in work:
            base[k] = work[k]
    return base


def build_RP():
    LD_INCLUDED = []
    LD_EXCLUDED = []

    CFG_FILE_INT = "%s/cfg" % os.path.dirname(os.path.realpath(__file__))
    CFG_FILE_INT = os.path.normpath(CFG_FILE_INT)

    CFG_FILE_EXT = "%s/cfg" % os.getcwd()
    CFG_FILE_EXT = os.path.normpath(CFG_FILE_EXT)

    envrole = cfg.envrole
    stacktype = cfg.stacktype
    brand = cfg.brand

    RP_base = {}

    # dynamically populate RP_base Dict from ENV_BASE and cfg.regions
    for n in cfg.ENV_BASE:
        RP_base[n] = {}
        for m in cfg.regions:
            RP_base[n][m] = {}

    cfg.RP_base = RP_base

    def _get_RP_base_keys():
        RP_base_keys = ["global"]
        for n, v in RP_base.items():
            RP_base_keys.append(n)
            for m, w in v.items():
                RP_base_keys.append(m)

        return RP_base_keys + [stacktype, envrole]

    RP_base_keys = _get_RP_base_keys()

    class Loader(yaml.Loader):
        def __init__(self, stream):
            # This way for include relative to file with include statement
            self._root_current = os.path.split(stream.name)[0]
            # This way for include BASE relative on BASE dir
            self._root_base = os.path.join(CFG_FILE_INT, "BASE")
            # This way for include relative on BASE EXT dir
            self._root_base_ext = os.path.join(CFG_FILE_EXT, "BASE")
            # This way for include relative on brand EXT dir
            self._root_brand_ext = os.path.join(CFG_FILE_EXT, brand)

            # try to find out if source file is in a subfolder
            if self._root_base in self._root_current:
                suffix = self._root_current.replace(self._root_base, "")
            elif self._root_base_ext in self._root_current:
                suffix = self._root_current.replace(self._root_base_ext, "")
            else:
                suffix = self._root_current.replace(self._root_brand_ext, "")

            # self.root_current_suffix will be empty if source file is in root
            self.root_current_suffix = os.path.basename(suffix)
            if self.root_current_suffix.upper() in cfg.STACK_TYPES:
                # set to empty even if UPPERCASE subfolders is in
                # cfg.STACK_TYPES to not be searched for include files
                self.root_current_suffix = ""

            self.stream = stream
            super(Loader, self).__init__(stream)
            Loader.add_constructor("!include", Loader.include)
            Loader.add_constructor("!exclude", Loader.exclude)

        def exclude(self, node):
            if isinstance(node, yaml.SequenceNode):
                for filename in self.construct_sequence(node):
                    LD_EXCLUDED.append(filename)

        def include(self, node):
            if isinstance(node, yaml.SequenceNode):
                result = []
                for filename in self.construct_sequence(node):
                    if filename in LD_EXCLUDED + LD_INCLUDED:
                        # a yml file can be included only once
                        continue
                    LD_INCLUDED.append(filename)

                    # search for include in files in roots
                    for path in [
                        self._root_base,
                        self._root_base_ext,
                        self._root_brand_ext,
                    ]:
                        if "/" not in filename and self.root_current_suffix:
                            # for file in subfolder that include file without a path
                            # search only in current subfolder
                            path = os.path.join(path, self.root_current_suffix)

                        contents = self.extractFile(filename, path)
                        if contents:
                            result.append(contents)
                return result
            else:
                print("Error:: unrecognised node type in !include statement")
                raise yaml.constructor.ConstructorError

        def extractFile(self, filename, root):
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r") as f:
                    return yaml.load(f, Loader)
            except IOError:
                pass

    def process_cfg(cfg, envs, skip=True):
        if hasattr(cfg, "items"):
            # This method allow to delete items from a dictionary
            # while iterating over it
            for k in list(cfg):
                v = cfg[k]
                # for final values
                if isinstance(v, (str, int, list)) and not k.startswith("IBoxLoader"):
                    yield {k: v}
                # for empty dict in common.yml
                if isinstance(v, dict) and len(v) == 0:
                    yield {k: v}
                # for recursively descending in env/region role dict.
                # list is needed for IBoxLoader include list.
                if k in envs and isinstance(v, (dict, list)):
                    if k in ["IBoxLoader", "IBoxLoaderAfter"]:
                        # IBoxLoader included dict processed by
                        # process_cfg keep skip = True
                        skip = True
                    else:
                        skip = False
                    try:
                        # after descending in env main key
                        # (not the one nested under region) delete key
                        # this way when envs include both (env and region)
                        # i do not process it again
                        if k in list(RP_base.keys()):
                            del cfg[k]
                    except Exception:
                        pass
                    for result in process_cfg(v, envs, skip=skip):
                        yield result
                if skip:
                    # Here i do not have yet encountered a envs key
                    # skip properties until i find it.
                    # Useful for using yaml anchors before global key
                    continue
                # for recursively descending in dict not in RP_base_keys
                # (env/region/envrole/stacktype)
                # (final key is the concatenation of traversed dict keys)
                if k not in RP_base_keys and isinstance(v, dict):
                    for j, w in v.items():
                        for result in process_cfg({f"{k}{j}": w}, envs, skip=skip):
                            yield result
        if isinstance(cfg, list):
            for n in cfg:
                for result in process_cfg(n, envs, skip=skip):
                    yield result

    def replace_not_allowed_char(s):
        # CF Mapping allow for index only alfanumeric char
        # this way i can specify more "clear" name
        # for index in CloudFormation behaviours
        key = str(s)
        for s, w in cfg.CLF_PATH_PATTERN_REPLACEMENT.items():
            key = key.replace(s, w)

        return int(key) if key.isdigit() else key

    def merge_RP(data):
        def _process(key, data, RP, merge=True):
            key = str(key)

            if key.startswith("/"):
                # for CFront Behaviors
                key = replace_not_allowed_char(key)
            if key.endswith("**"):
                # ** is used to replace existing dict instead of merging it
                f_key = key.replace("**", "")
                if isinstance(RP.get(f_key), dict):
                    # replace key only if same key already exist and is a dict
                    key = f_key
                merge = False

            if merge and isinstance(RP.get(key), dict):
                # RP[key] already exist as a dict, try merging
                RP[key] = merge_dict(RP[key], _recurse(data))
            elif isinstance(RP.get(key), str) and RP[key] == "IBOX_SKIP_FUNC":
                # if key need to be skipped using IBOX_SKIP_FUNC avoid overwriting it
                pass
            elif key in cfg.MERGE_RP_KEEP_AS_LIST and isinstance(data, list):
                # this keys need to stay as a list of dicts
                RP[key] = data
            else:
                RP[key] = _recurse(data)

        def _recurse(data):
            RP = {}
            if isinstance(data, dict):
                # data is a dict
                for n, v in data.items():
                    _process(n, v, RP)
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                # data is a list of dicts
                for v in data:
                    for m, w in v.items():
                        _process(m, w, RP)
            else:
                RP = data
            return RP

        return _recurse(data)

    def read_yaml(file_type, brand, base_dir, stacktype=""):
        cfg_file = os.path.join(base_dir, brand, stacktype.upper(), f"{file_type}.yml")

        try:
            with open(cfg_file, "r") as ymlfile:
                cfg = yaml.load(ymlfile, Loader=Loader)

                return cfg
        except IOError:
            return {}

    def inject_ibox_base(RP, root=""):
        base_key = "IBOX_BASE"
        for main_key in list(RP.keys()):
            main_key_full = f"{root}{main_key}"
            main_key_value = RP[main_key]
            if isinstance(main_key_value, dict) and base_key in main_key_value:
                base_key_value = main_key_value[base_key]
                base_key_value["IBOX_BASE_REF"] = True

                for resource_key, resource_key_value in main_key_value.items():
                    if (
                        resource_key == base_key
                        or "IBOX_BASE_SKIP" in resource_key_value
                    ):
                        continue
                    # inject in cfg key/value
                    RP_to_cfg(
                        base_key_value,
                        prefix=f"{main_key_full}{resource_key}",
                        overwrite=False,
                    )

                    # inject in existing structure
                    merged = merge_dict(
                        copy.deepcopy(base_key_value), resource_key_value
                    )
                    # need to do it this way to keep the "link" between existing dict keys and values
                    for n, v in merged.items():
                        RP[main_key][resource_key][n] = v
                del RP[main_key][base_key]

            if isinstance(main_key_value, dict):
                inject_ibox_base(main_key_value, root=main_key_full)

    def get_RP(yaml_cfg):
        cfg_keys = ["IBoxLoader", "IBoxLoaderAfter"]

        def _parse_yaml(conf, envs=[]):
            parsed_yaml = {}
            for value in process_cfg(conf, envs):
                for k, v in value.items():
                    try:
                        # if v is a list of dict and the same key (k) already
                        # exist, final value is the sum of the list (of dicts)
                        if isinstance(v[0], dict):
                            parsed_yaml[k] = parsed_yaml[k] + v
                        else:
                            raise
                    except Exception:
                        parsed_yaml[k] = v
            return parsed_yaml

        def get_RP_tree():
            RP_list = []

            for cfg_type, ctv in yaml_cfg.items():
                for read_yaml in ctv:
                    parsed_global = _parse_yaml(read_yaml, cfg_keys + ["global"])
                    RP_list.append(parsed_global)

            # merge keys value
            RP = merge_RP(RP_list)

            return RP

        def get_RP_map():
            RP = copy.deepcopy(RP_base)
            mapped_keys = []

            # I build the cfg to build the mappings for env/region
            for env in list(RP):
                rvalue = RP[env]
                env_cfg = {}
                # first the configuration under the env key
                for cfg_type, ctv in yaml_cfg.items():
                    for read_yaml in ctv:
                        env_cfg.update(_parse_yaml(read_yaml, cfg_keys + [env]))
                # then the one under region + env keys
                for region in list(rvalue.keys()):
                    RP[env][region] = copy.deepcopy(env_cfg)
                    for cfg_type, ctv in yaml_cfg.items():
                        for read_yaml in ctv:
                            RP[env][region].update(
                                _parse_yaml(
                                    copy.deepcopy(read_yaml), cfg_keys + [env, region]
                                )
                            )
                    # create list of all mapped keys
                    for key in list(RP[env][region]):
                        if hasattr(cfg, f"{key}@"):
                            # if there is key in RP_tree/cfg and it endswith "@"
                            # skip mapped values and update cfg.fixedvalues and RP
                            cfg.fixedvalues[key] = getattr(cfg, f"{key}@")
                            del RP[env][region][key]
                        elif hasattr(cfg, key) and RP[env][region][key] == getattr(
                            cfg, key
                        ):
                            # if value is equal to the global one, delete the key
                            del RP[env][region][key]
                        elif key not in mapped_keys:
                            # only add if not already present
                            mapped_keys.append(key)
                            # delete the fixed one
                            try:
                                del cfg.fixedvalues[key]
                            except Exception:
                                pass

            cfg.mappedvalues = mapped_keys
            return RP

        # RP_tree represent the resources structure and it's configuration.
        RP_tree = get_RP_tree()

        # Read RP_tree and put a flat key/value configuration in cfg.
        cfg.fixedvalues = {}
        RP_to_cfg(RP_tree)

        # Inject IBOX_BASE configurations
        inject_ibox_base(RP_tree)

        # Create the mapping for env/region.
        RP_map = get_RP_map()

        return RP_tree, RP_map

    # End inner methods and begin of main code.

    # envrole type files must be read first
    yaml_role = [
        read_yaml(envrole, "BASE", CFG_FILE_INT, stacktype),
        read_yaml(envrole, "BASE", CFG_FILE_EXT, stacktype),
        read_yaml(envrole, brand, CFG_FILE_EXT, stacktype),
    ]

    yaml_cfg = {
        "common": [
            read_yaml("common", "BASE", CFG_FILE_INT),
            read_yaml("common", "BASE", CFG_FILE_EXT),
            read_yaml("common", brand, CFG_FILE_EXT),
        ],
        "type": [
            read_yaml("TYPE", "BASE", CFG_FILE_INT, stacktype),
            read_yaml("TYPE", "BASE", CFG_FILE_EXT, stacktype),
            read_yaml("TYPE", brand, CFG_FILE_EXT, stacktype),
        ],
        "role": yaml_role,
    }

    cfg.RP_tree, cfg.RP_map = get_RP(yaml_cfg)

    if cfg.debug:
        print("########## RP ######### START #####")
        pprint(cfg.RP_tree)
        print("########## RP ######### END #######")

        print("########## EXCLUDED ####### START #####")
        pprint(LD_EXCLUDED)
        print("########## EXCLUDED ####### END #######")

        print("########## INCLUDED ####### START #####")
        pprint(LD_INCLUDED)
        print("########## INCLUDED ####### END #######")

        print("########## FIXEDVALUES ######### START #####")
        pprint(cfg.fixedvalues)
        print("########## FIXEDVALUES ######### END #######")

        print("########## MAPPEDVALUES ######### START #####")
        pprint(cfg.RP_map)
        print("########## MAPPEDVALUES ######### END #######")
