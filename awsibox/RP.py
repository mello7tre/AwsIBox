import yaml
import yaml.constructor
import sys
import os
import copy
import json
import logging
from pprint import pprint, pformat

from . import cfg


def build_RP():
    LD_INCLUDED = []
    LD_EXCLUDED = []

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

    def _get_RP_base_keys():
        RP_base_keys = ['global']
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
                # set to empty even if UPPERCASE subfolders is in
                # cfg.STACK_TYPES to not be searched for include files
                self.root_current_suffix = ''

            self.stream = stream
            super(Loader, self).__init__(stream)
            Loader.add_constructor('!include', Loader.include)
            Loader.add_constructor('!exclude', Loader.exclude)

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
                    for path in [self._root_base,
                                 self._root_base_ext,
                                 self._root_brand_ext]:
                        contents = self.extractFile(filename, path)
                        if contents:
                            result.append(contents)
                        if self.root_current_suffix:
                            # search in subfolder too
                            contents = self.extractFile(filename, os.path.join(
                                path, self.root_current_suffix))
                            if contents:
                                result.append(contents)
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

    def process_cfg(cfg, envs, check_root=None):
        if hasattr(cfg, 'items'):
            # This method allow to delete items from a dictionary
            # while iterating over it
            for k in list(cfg):
                v = cfg[k]
                # for final values
                if (isinstance(v, (str, int, list))
                        and not k.startswith('IBoxLoader')):
                    yield {k: v}
                # for empty dict in common.yml
                if isinstance(v, dict) and len(v) == 0:
                    yield {k: v}
                # for recursively descending in env/region role dict.
                # list is needed for IBoxLoader include list.
                if k in envs and isinstance(v, (dict, list)):
                    if k in ['IBoxLoader', 'IBoxLoaderAfter']:
                        # IBoxLoader included dict processed by
                        # process_cfg have check_root = True
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
                    for result in process_cfg(v, envs, **kwargs):
                        yield result
                if check_root:
                    # Here i do not have yet encountered a envs key in an
                    # IBoxLoader included dict, skip properties until i find it
                    continue
                # for recursively descending in dict not in RP_base_keys
                # (env/region/envrole/stacktype)
                # (final key is the concatenation of traversed dict keys)
                if k not in RP_base_keys and isinstance(v, dict):
                    for j, w in v.items():
                        for result in process_cfg({f'{k}{j}': w}, envs):
                            yield result
        if isinstance(cfg, list):
            for n in cfg:
                for result in process_cfg(n, envs, check_root=check_root):
                    yield result

    def replace_not_allowed_char(s):
        # CF Mapping allow for index only alfanumeric char
        # this way i can specify more "clear" name
        # for index in CloudFormation behaviours
        key = str(s)
        for s, w in cfg.CLF_PATH_PATTERN_REPLACEMENT.items():
            key = key.replace(s, w)

        return int(key) if key.isdigit() else key

    def get_RP_for_envs(data):
        def _merge(base, work):
            if isinstance(work, (str, list)) or not base:
                return work
            keys = dict(list(base.items()) + list(work.items())).keys()
            for k in keys:
                if (isinstance(base.get(k), dict)
                        and isinstance(work.get(k), dict)):
                    base[k] = _merge(base[k], work[k])
                elif k.endswith('++') and isinstance(work.get(k), list):
                    # ++ is used to append elements to an existing key
                    base[k.replace('++', '')] += work[k]
                elif k in work:
                    base[k] = work[k]
            return base

        def _process(key, data, RP, merge=True):
            key = str(key)

            if key.startswith('/'):
                # for CFront Behaviors
                key = replace_not_allowed_char(key)
            if key.endswith('**'):
                # ** is used to replace existing dict instead of merging it
                key = key.replace('**', '')
                merge = False

            if merge and isinstance(RP.get(key), dict):
                # RP[key] already exist as a dict, try merging
                RP[key] = _merge(RP[key], _recurse(data))
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

    def read_yaml(file_type, brand, base_dir, stacktype=''):
        cfg_file = os.path.join(
            base_dir, brand, stacktype.upper(), f'{file_type}.yml')

        try:
            with open(cfg_file, 'r') as ymlfile:
                cfg = yaml.load(ymlfile, Loader=Loader)

                return cfg
        except IOError:
            return {}

    def merge_cfg(cfgs, cfg_key, list_base=None):
        RP_list = copy.deepcopy(list_base) if list_base else []

        def _parse_cfg(cfg, envs=[]):
            parsed_cfg = {}
            for value in process_cfg(cfg, envs):
                for k, v in value.items():
                    try:
                        # if v is a list of dict and the same key (k) already
                        # exist, final value is the sum of the list (of dicts)
                        if isinstance(v[0], dict):
                            parsed_cfg[k] = parsed_cfg[k] + v
                        else:
                            raise
                    except Exception:
                        parsed_cfg[k] = v
            return parsed_cfg

        for cfg, v in cfgs.items():
            for c in v:
                keys = ['IBoxLoader', 'IBoxLoaderAfter'] + cfg_key[cfg]
                RP_list.append(_parse_cfg(c, keys))

        # RP_list is now a list of dict
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
                                # use IBOX_BASE (or values in cfg.BASE_CFGS)
                                for j, w in base_value.items():
                                    j_current = base_cfgs[n].get(j)
                                    if j_current and isinstance(
                                            j_current, list):
                                        # if property is a list extend it
                                        base_cfgs[n][j].extend(w)
                                    else:
                                        base_cfgs[n][j] = w
                                v.remove(k)
                        if not c[n]:
                            del c[n]

        for n, v in key_names.items():
            values = []
            # is better "set(v):" but change order so for now keep it
            for m in v:
                values.append({m: base_cfgs[n]})
            if values:
                cfg_cmm.insert(0, {n: values})

    def get_RP(cfgs):
        RP = copy.deepcopy(RP_base)

        cfg_key_cmm = {
            'common': ['global'],
            'type': ['global'],
            'role': ['global'],
        }

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

# End inner methods

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

    RP = get_RP(cfgs)

    # print(RP['dev']['eu-west-1']['CloudFrontCacheBehaviors']
    #    [2]['QueryStringCacheKeys'])
    if cfg.debug:
        print('##########RP#########START#####')
        pprint(RP)
        print('##########RP#########END#######')

        print('##########EXCLUDED#######START#####')
        pprint(LD_EXCLUDED)
        print('##########EXCLUDED#######END#######')

        print('##########INCLUDED#######START#####')
        pprint(LD_INCLUDED)
        print('##########INCLUDED#######END#######')

    cfg.RP = RP
    cfg.RP_cmm = RP['cmm']['cmm']

    set_cfg()
