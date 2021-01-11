import yaml
import yaml.constructor
import sys
import os
import copy
import json
import logging
from collections.abc import Mapping
from pprint import pprint, pformat

from . import cfg


class Loader(yaml.Loader):
    def __init__(self, stream):
        # This way for include relative to file with include statement
        self._root_current = os.path.split(stream.name)[0]
        # This way for include BASE relative on BASE dir
        self._root_base = os.path.join(CFG_FILE_INT, 'BASE')
        # This way for include relative on BASE EXT dir
        self._root_base_ext = os.path.join(CFG_FILE_EXT, 'BASE')
        # This way for include relative on brand EXT dir
        self._root_brand_ext = os.path.join(CFG_FILE_EXT, brand)

        # try to find out if source file is in a subfolder
        if self._root_base in self._root_current:
            suffix = self._root_current.replace(self._root_base, '')
        elif self._root_base_ext in self._root_current:
            suffix = self._root_current.replace(self._root_base_ext, '')
        else:
            suffix = self._root_current.replace(self._root_brand_ext, '')

        # self.root_current_suffix will be empty if source file is in root
        self.root_current_suffix = os.path.basename(suffix)
        if self.root_current_suffix.upper() in cfg.STACK_TYPES:
            # set to empty even if UPPERCASE subfolders is in cfg.STACK_TYPES
            # so that they are not searched for include files
            self.root_current_suffix = ''

        self.stream = stream
        super(Loader, self).__init__(stream)
        Loader.add_constructor('!include', Loader.include)
        Loader.add_constructor('!import', Loader.include)
        Loader.add_constructor('!exclude', Loader.exclude)

    def exclude(self, node):
        global exclude_list
        global include_list
        if isinstance(node, yaml.ScalarNode):
            exclude_list.append(node)
        elif isinstance(node, yaml.SequenceNode):
            for filename in self.construct_sequence(node):
                exclude_list.append(filename)

    def include(self, node):
        if isinstance(node, yaml.ScalarNode) and node not in (
                exclude_list + include_list):
            # a yml file can be included only once
            include_list.append(node)
            return self.extractFile(
                self.construct_scalar(node), self._root_current)

        elif isinstance(node, yaml.SequenceNode):
            result = []
            for filename in self.construct_sequence(node):
                if filename in exclude_list + include_list:
                    continue
                include_list.append(filename)

                # search for include in files in roots
                for path in [self._root_base,
                             self._root_base_ext,
                             self._root_brand_ext]:
                    result.append(self.extractFile(filename, path))
                    if self.root_current_suffix:
                        # search in subfolder too
                        result.append(
                            self.extractFile(filename, os.path.join(
                                path, self.root_current_suffix)))
            return result

        elif isinstance(node, yaml.MappingNode):
            result = {}
            for k, v in self.construct_mapping(node).items():
                if k in exclude_list + include_list:
                    continue
                include_list.append(k)
                result[k] = self.extractFile(v, self._root_current)
            return result

        else:
            print('Error:: unrecognised node type in !include statement')
            raise yaml.constructor.ConstructorError

    def extractFile(self, filename, root):
        filepath = os.path.join(root, filename)
        try:
            with open(filepath, 'r') as f:
                return yaml.load(f, Loader)
        except IOError:
            pass


def replace_not_allowed_char(s):
    key = str(s)
    for s, w in cfg.CLF_PATH_PATTERN_REPLACEMENT.items():
        key = key.replace(s, w)

    return int(key) if key.isdigit() else key


def gen_dict_extract(cfg, envs, check_root=None):
    global enforce_list
    if hasattr(cfg, 'items'):
        # This method allow to delete items from a dictionary
        # while iterating over it
        for k in list(cfg):
            v = cfg[k]
            # for final values
            if (isinstance(v, (str, int, list)) and
                    not k.startswith('IBoxLoader')):
                if k in enforce_list:
                    continue
                elif k.endswith('_IBOXENFORCE'):
                    k = k.replace('_IBOXENFORCE', '')
                    enforce_list.append(k)
                yield {k: v}
            # for empty dict in common.yml
            if isinstance(v, dict) and len(v) == 0:
                yield {k: v}
            # for recursively descending in env/region role dict.
            # List is needed for IBoxLoader include list.
            if k in envs and isinstance(v, (dict, list)):
                if k in ['IBoxLoader', 'IBoxLoaderAfter']:
                    # IBoxLoader included dict processed by
                    # gen_dict_extract have check_root = True
                    kwargs = {'check_root': True}
                else:
                    kwargs = {}
                try:
                    # after descending in env main key
                    # (not the one nested under region) delete key
                    # this way when envs include both (env and region)
                    # i do not process it again
                    if k in list(RP_base.keys()):
                        del cfg[k]
                except Exception:
                    pass
                for result in gen_dict_extract(v, envs, **kwargs):
                    yield result
            if check_root:
                # If iam here means i do not have yet encountered a envs key in
                # an IBoxLoader included dict, so skip properties until i find
                continue
            # for recursively descending in dict not in RP_base_keys
            # (env/region/envrole/stacktype)
            # (final key is the concatenation of traversed dict keys)
            if k not in RP_base_keys and isinstance(v, dict):
                for j, w in v.items():
                    for result in gen_dict_extract({f'{k}{j}': w}, envs):
                        yield result
    if isinstance(cfg, list):
        for n in cfg:
            for result in gen_dict_extract(n, envs, check_root=check_root):
                yield result


def my_merge_dict(basedict, workdict):
    if isinstance(workdict, (str, list)):
        return workdict
    if len(basedict) > 0:
        sumdict = dict(list(basedict.items()) + list(workdict.items()))
    else:
        basedict.update(workdict)
        return dict(list(workdict.items()))

    for k in sumdict.keys():
        try:
            is_dict = isinstance(workdict[k], dict)
            is_map = isinstance(basedict[k], Mapping)
        except Exception:
            is_dict = False
            is_map = False

        # Trick to be able to add an element
        # to a previuosly created/defined list.
        # I can centralize some general iampolicy in ecs-cluster and
        # attach them to RoleInstance, adding element to ManagedPolicyArns,
        # preserving the base ones
        try:
            ibox_add_to_list = (workdict[k][0] == 'IBOXADDTOLIST')
        except Exception:
            ibox_add_to_list = False

        if is_dict and is_map:
            my_merge_dict(basedict[k], workdict[k])
        elif ibox_add_to_list:
            del workdict[k][0]
            basedict[k] += workdict[k]
        elif k in workdict:
            basedict[k] = workdict[k]
        else:
            pass

    return basedict


def get_RP_for_envs(value):
    RP = {}

    try:
        is_dict = isinstance(value[0], dict)
    except Exception:
        is_dict = False

    if hasattr(value, 'items'):
        for d, v in value.items():
            RP[d] = get_RP_for_envs(v)
    elif is_dict:
        for d, v in enumerate(value):
            for i, j in v.items():
                # Trick to overwrite a key - needed if it's value is a dict
                # to avoid that previous dict values are merged.
                if str(i).endswith('**'):
                    key = i.replace('**', '')
                    RP[key] = get_RP_for_envs(j)
                    continue
                # CF Mapping allow for index only alfanumeric char,
                # this way i can specify more "clear" name
                # for index in CloudFormation behaviours
                key = replace_not_allowed_char(i)
                # RP[key] already exist as a dict, try merging
                if key in RP and isinstance(RP[key], dict):
                    RP[key] = my_merge_dict(RP[key], get_RP_for_envs(j))
                else:
                    RP[key] = get_RP_for_envs(j)
    elif isinstance(value, list):
        RP = list(value)
    else:
        RP = value

    return RP


def read_yaml(file_type, brand, base_dir, stacktype=''):
    cfg_file = os.path.join(
        base_dir, brand, stacktype.upper(), f'{file_type}.yml')

    try:
        with open(cfg_file, 'r') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=Loader)

            return cfg
    except IOError:
        return {}


def parse_cfg(cfg, envs=[]):
    parsed_cfg = {}

    for value in gen_dict_extract(cfg, envs):
        for k, v in value.items():
            try:
                if isinstance(v[0], dict):
                    parsed_cfg[k] = parsed_cfg[k] + v
                else:
                    raise
            except Exception:
                parsed_cfg[k] = v

    return parsed_cfg


def merge_cfg(cfgs, cfg_key, list_base=None):
    RP_list = copy.deepcopy(list_base) if list_base else []

    for cfg, v in cfgs.items():
        for c in v:
            keys = ['IBoxLoader', 'IBoxLoaderAfter'] + cfg_key[cfg]
            parsed_cfg = parse_cfg(c, keys)
            RP_list.append(parsed_cfg)

    return RP_list


def prepend_base_cfgs(cfg_cmm):
    base_cfgs = {}
    key_names = {}
    for c in cfg_cmm:
        if isinstance(c, dict):
            for n in list(c):
                # need to delete items while iterating
                v = c[n]
                if n in cfg.BASE_CFGS:
                    if n not in base_cfgs:
                        base_cfgs[n] = {}
                    if n not in key_names:
                        key_names[n] = []
                    base_key_value = cfg.BASE_CFGS[n]
                    for k in list(v):
                        try:
                            base_value = k[base_key_value]
                        except Exception:
                            if isinstance(base_key_value, dict):
                                # use dict value in cfg.BASE_CFGS
                                base_cfgs[n] = base_key_value
                            key_names[n].extend(list(k.keys()))
                        else:
                            # use IBOXBASE (or other value in cfg.BASE_CFGS)
                            for j, w in base_value.items():
                                base_cfgs[n][j] = w
                            v.remove(k)
                    if not c[n]:
                        del c[n]

    for n, v in key_names.items():
        values = []
        # can be optimized with "set(v):" but change order so for now keep it
        for m in v:
            values.append({m: base_cfgs[n]})
        cfg_cmm.insert(0, {n: values})


def get_RP(cfgs):
    RP = copy.deepcopy(RP_base)

    cfg_key_cmm = {
        'common': ['global'],
        'type': [stacktype, 'global'],
        'role': [envrole, 'global'],
    }

    RP_list = []

    cfg_merge_cmm = merge_cfg(cfgs, cfg_key_cmm)

    # Prepend base config from awsibox/cfg.py BASE_CFGS
    prepend_base_cfgs(cfg_merge_cmm)

    RP['cmm']['cmm'] = get_RP_for_envs(cfg_merge_cmm)

    for env, rvalue in RP.items():
        if env == 'cmm':
            continue

        cfg_key_env = {
            'common': [env],
            'type': [env],
            'role': [env],
        }

        cfg_merge_env = merge_cfg(cfgs, cfg_key_env)

        for region in rvalue.keys():

            cfg_key_region = {
                'common': [region],
                'type': [region],
                'role': [region],
            }

            cfg_key_env_region = {
                'common': [env, region],
                'type': [env, region],
                'role': [env, region],
            }

            cfg_merge_region = merge_cfg(
                cfgs, cfg_key_region, cfg_merge_env)
            cfg_merge_env_region = merge_cfg(
                cfgs, cfg_key_env_region, cfg_merge_region)

            RP[env][region] = get_RP_for_envs(cfg_merge_env_region)

    return(RP)


def get_RP_base_keys():
    RP_base_keys = ['global']
    for n, v in RP_base.items():
        RP_base_keys.append(n)
        for m, w in v.items():
            RP_base_keys.append(m)

    return RP_base_keys + [stacktype, envrole]


def set_cfg():
    def RP_to_cfg(key):
        if hasattr(key, 'items'):
            for k, v in key.items():
                setattr(cfg, k, v)
                # recursively traverse dict
                # keys name are the concatenation of traversed dict keys
                if isinstance(v, dict):
                    for j, w in v.items():
                        RP_to_cfg({f'{k}{j}': w})

    # for n, v in cfg.RP_cmm.items():
    #     setattr(cfg, n, v)
    RP_to_cfg(cfg.RP_cmm)

    # set generic attribute based on condition:

    # LoadBalancerClassic
    try:
        cfg.LoadBalancerClassic
    except Exception:
        cfg.LoadBalancerClassic = []

    # LoadBalancerApplication
    try:
        cfg.LoadBalancerApplication
    except Exception:
        cfg.LoadBalancerApplication = []

    # LoadBalancer
    cfg.LoadBalancer = None
    for n in ['LoadBalancerClassic', 'LoadBalancerApplication']:
        try:
            getattr(cfg, n)
        except Exception:
            pass
        else:
            cfg.LoadBalancer = True

    # LoadBalancerClassicExternal LoadBalancerClassicInternal
    cfg.LoadBalancerClassicExternal = None
    cfg.LoadBalancerClassicInternal = None
    try:
        cfg.LoadBalancerClassic
    except Exception:
        pass
    else:
        if 'External' in cfg.LoadBalancerClassic:
            cfg.LoadBalancerClassicExternal = True
        if 'Internal' in cfg.LoadBalancerClassic:
            cfg.LoadBalancerClassicInternal = True

    # LoadBalancerApplicationExternal LoadBalancerApplicationInternal
    cfg.LoadBalancerApplicationExternal = False
    cfg.LoadBalancerApplicationInternal = False
    try:
        cfg.LoadBalancerApplication
    except Exception:
        pass
    else:
        if 'External' in cfg.LoadBalancerApplication:
            cfg.LoadBalancerApplicationExternal = True
        if 'Internal' in cfg.LoadBalancerApplication:
            cfg.LoadBalancerApplicationInternal = True

    # RecordSet
    cfg.RecordSetExternal = None
    cfg.RecordSetInternal = None
    if 'External' in cfg.RecordSet:
        cfg.RecordSetExternal = True
    if 'Internal' in cfg.RecordSet:
        cfg.RecordSetInternal = True


def build_RP():
    global envrole
    global stacktype
    global RP_base
    global RP_base_keys
    global brand
    global CFG_FILE_INT
    global CFG_FILE_EXT
    global enforce_list
    global exclude_list
    global include_list

    enforce_list = []
    exclude_list = []
    include_list = []

    CFG_FILE_INT = '%s/cfg' % os.path.dirname(os.path.realpath(__file__))
    CFG_FILE_INT = os.path.normpath(CFG_FILE_INT)

    CFG_FILE_EXT = '%s/cfg' % os.getcwd()
    CFG_FILE_EXT = os.path.normpath(CFG_FILE_EXT)

    envrole = cfg.envrole
    stacktype = cfg.stacktype
    brand = cfg.brand

    RP_base = {
        'cmm': {
            'cmm': {}
        }
    }

    # dynamically populate RP_base Dict from ENV_BASE and cfg.regions
    for n in cfg.ENV_BASE:
        RP_base[n] = {}
        for m in cfg.regions:
            RP_base[n][m] = {}

    cfg.RP_base = RP_base

    cfg_role = [
        read_yaml(envrole, 'BASE', CFG_FILE_INT, stacktype),
        read_yaml(envrole, 'BASE', CFG_FILE_EXT, stacktype),
        read_yaml(envrole, brand, CFG_FILE_EXT, stacktype),
    ]

    cfgs = {
        'common': [
            read_yaml('common', 'BASE', CFG_FILE_INT),
            read_yaml('common', 'BASE', CFG_FILE_EXT),
            read_yaml('common', brand, CFG_FILE_EXT),
        ],
        'type': [
            read_yaml('TYPE', 'BASE', CFG_FILE_INT, stacktype),
            read_yaml('TYPE', 'BASE', CFG_FILE_EXT, stacktype),
            read_yaml('TYPE', brand, CFG_FILE_EXT, stacktype),
        ],
        'role': cfg_role,
    }

    RP_base_keys = get_RP_base_keys()

    RP = get_RP(cfgs)

    # print(RP['dev']['eu-west-1']['CloudFrontCacheBehaviors']
    #    [2]['QueryStringCacheKeys'])
    if cfg.debug:
        print('##########RP#########START#####')
        pprint(RP)
        print('##########RP#########END#######')
        print('##########ENFORCED######START#####')
        pprint(enforce_list)
        print('##########ENFORCED######END#######')
        print('##########EXCLUDED#######START#####')
        pprint(exclude_list)
        print('##########EXCLUDED#######END#######')
        print('##########INCLUDED#######START#####')
        pprint(include_list)
        print('##########INCLUDED#######END#######')

    cfg.RP = RP
    cfg.RP_cmm = RP['cmm']['cmm']

    set_cfg()
