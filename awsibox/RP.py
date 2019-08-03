import yaml
import yaml.constructor
import sys
import os
import copy
import json
import logging
from collections import OrderedDict, Mapping
from pprint import pprint, pformat

import cfg


def show_odict(odict):
    print(json.dumps(odict, indent=4))


# We also need to load mappings in order
# Based on https://gist.github.com/844388
def construct_ordereddict(loader, node):
    data = OrderedDict()
    yield data
    value = construct_mapping(loader, node)
    data.update(value)


def construct_mapping(self, node, deep=False):
    if isinstance(node, yaml.MappingNode):
        self.flatten_mapping(node)
    else:
        raise yaml.constructor.ConstructorError(
            None, None, 'expected a mapping node, but found %s' % node.id, node.start_mark)

    mapping = OrderedDict()
    for key_node, value_node in node.value:
        key = self.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError, exc:
            raise yaml.constructor.ConstructorError(
                'while constructing a mapping', node.start_mark,
                'found unacceptable key (%s)' % exc, key_node.start_mark)
        value = self.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


class Loader(yaml.Loader):
    def __init__(self, stream):
        # This way for include relative to file with include statement
        self._root_current = os.path.split(stream.name)[0]
        # This way for include BASE relative on BASE dir
        self._root_base = os.path.join(CFG_FILE_INT, 'BASE')
        # This way for include relative on BASE EXT dir
        self._root_brand_base = os.path.join(CFG_FILE_EXT, 'BASE')
        # This way for include relative on brand EXT dir
        self._root_brand_ext = os.path.join(CFG_FILE_EXT, brand)
        self.stream = stream
        super(Loader, self).__init__(stream)
        Loader.add_constructor('!include', Loader.include)
        Loader.add_constructor('!import',  Loader.include)

    def include(self, node):
        if   isinstance(node, yaml.ScalarNode):
            return self.extractFile(self.construct_scalar(node), self._root_current)

        elif isinstance(node, yaml.SequenceNode):
            result = []
            for filename in self.construct_sequence(node):
                # if including Ext cfg try to include BASE file from CFG_FILE_INT too
                if CFG_FILE_EXT in self.stream.name:
                    result.append(self.extractFile(filename, self._root_base))
                result.append(self.extractFile(filename, self._root_current))
                # try to include BASE ext too
                result.append(self.extractFile(filename, self._root_brand_base))
                # try to include brand ext too
                result.append(self.extractFile(filename, self._root_brand_ext))
                # result += self.extractFile(filename)
            return result

        elif isinstance(node, yaml.MappingNode):
            result = {}
            for k,v in self.construct_mapping(node).iteritems():
                result[k] = self.extractFile(v, self._root_current)
            return result

        else:
            print "Error:: unrecognised node type in !include statement"
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
    for s, w in {
            '/': 'SLASH',
            '*': 'STAR',
            '-': 'HYPH',
            '?': 'QUEST',
            '.': 'DOT',
            '_': 'USCORE',
    }.iteritems():
        key = key.replace(s, w)

    return int(key) if key.isdigit() else key


def gen_dict_extract(cfg, envs):
    if hasattr(cfg, 'iteritems'):
        for k, v in cfg.iteritems():
            # for final values
            if isinstance(v, (str, int, list)) and (k != 'include' and k != 'includeAfter'):
                yield {k: v}
            # for empty dict in common.yml
            if isinstance(v, dict) and len(v) == 0:
                yield {k: v}
            # for recursively descending in env/region role dict
            if k in envs and isinstance(v, (dict, list)):
                try:
                    # after descending in env main key (not the one nested under region) delete key
                    # this way when envs include both (env and region) i do not process it again
                    if k in RP_base.keys():
                        del cfg[k]
                except:
                    pass
                for result in gen_dict_extract(v, envs):
                    yield result
            # for recursively descending in dict not in RP_base_keys (env/region/envrole/stacktype) 
            # (final key is the concatenation of traversed dict keys)
            if k not in RP_base_keys and isinstance(v, (dict)):
                for j, w in v.iteritems():
                    for result in gen_dict_extract({k + j: w}, envs):
                        yield result
    if isinstance(cfg, list):
        for n in cfg:
            for result in gen_dict_extract(n, envs):
                yield result


def my_merge_dict(basedict, workdict):
    if isinstance(workdict, (str, list)):
        return workdict
    if len(basedict) > 0:
        sumdict = dict(basedict.items() + workdict.items())
    else:
        return dict(workdict.items())

    for k in sumdict.iterkeys():
        if k in workdict and isinstance(workdict[k], dict) and k in basedict and isinstance(basedict[k], Mapping):
            my_merge_dict(basedict[k], workdict[k])
        elif k in workdict:
            basedict[k] = workdict[k]
        #elif isinstance(basedict[k], dict) and 'PathPattern' in basedict[k] and basedict[k]['PathPattern'] == '':
        #    del basedict[k]
        else:
            pass

    return basedict


def get_RP_for_envs(value):
    RP = OrderedDict()

    if hasattr(value, 'iteritems'):
        for d, v in value.iteritems():
            RP[d] = get_RP_for_envs(v)
    elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], OrderedDict):
        for d, v in enumerate(value):
            for i, j in v.iteritems():
                # CF Mapping allow for index only alfanumeric char, this way i can specify more elegant index in CloudFormation behaviours
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


def read_yaml(file_type, brand, base_dir):
    cfg_file = os.path.join(base_dir, brand, file_type + '.yml')

    yaml.Loader.add_constructor(u'tag:yaml.org,2002:map', construct_ordereddict)
    try:
        with open(cfg_file, 'r') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=Loader)

            return cfg
    except IOError:
        return {}


def parse_cfg(cfg, envs=[]):
    odict = OrderedDict([])

    for value in gen_dict_extract(cfg, envs):
        for k, v in value.iteritems():
            if k in odict and isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                odict[k] = odict[k] + v
            else:
                odict[k] = v

    return odict


def merge_cfg(cfgs, cfg_key, list_base=None):
    RP_list = copy.deepcopy(list_base) if list_base else []

    for cfg, v in cfgs.iteritems():
        for c in v:
            keys = ['include', 'includeAfter'] + cfg_key[cfg]
            parsed_cfg = parse_cfg(c, keys)
            RP_list.append(parsed_cfg)

    return RP_list


def get_RP(cfgs):
    RP = copy.deepcopy(RP_base)

    cfg_key_cmm = {
        'common': ['global'],
        'type': [stacktype, 'global'],
        'role': [envrole, 'global'],
    }

    RP_list = []

    cfg_merge_cmm = merge_cfg(cfgs, cfg_key_cmm)

    RP['cmm']['cmm'] = get_RP_for_envs(cfg_merge_cmm)

    for env, rvalue in RP.iteritems():
        if env == 'cmm':
            continue

        cfg_key_env = {
            'common': [env],
            'type': [env],
            'role': [env],
        }

        cfg_merge_env = merge_cfg(cfgs, cfg_key_env)

        for region in rvalue.iterkeys():

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

            cfg_merge_region = merge_cfg(cfgs, cfg_key_region, cfg_merge_env)
            cfg_merge_env_region = merge_cfg(cfgs, cfg_key_env_region, cfg_merge_region)

            RP[env][region] = get_RP_for_envs(cfg_merge_env_region)

    return(RP)


def get_RP_base_keys():
    RP_base_keys = ['global']
    for n, v in RP_base.iteritems():
        RP_base_keys.append(n)
        for m, w in v.iteritems():
            RP_base_keys.append(m)

    return RP_base_keys + [stacktype, envrole]


def get_stack_type(cfgs):
    for c in cfgs:
        try:
            if isinstance(c[envrole], dict) and 'StackType' in c[envrole]:
                return c[envrole]['StackType']
        except KeyError:
            pass


global envrole
global stacktype
global RP_base
global RP_base_keys
global brand
global CFG_FILE_INT
global CFG_FILE_EXT

CFG_FILE_INT = '%s/cfg' % os.path.dirname(os.path.realpath(__file__))
CFG_FILE_INT = os.path.normpath(CFG_FILE_INT)

CFG_FILE_EXT = '%s/cfg' % os.getcwd()
CFG_FILE_EXT = os.path.normpath(CFG_FILE_EXT)

envrole = cfg.envrole
brand = cfg.brand
RP_base = cfg.RP_base

cfg_role = [
    read_yaml(envrole, 'BASE', CFG_FILE_INT),
    read_yaml(envrole, 'BASE', CFG_FILE_EXT),
    read_yaml(envrole, brand, CFG_FILE_EXT),
]

stacktype = get_stack_type(cfg_role)

if not stacktype:
    logging.error('StackType key not found for Role %s in paths: %s, %s', envrole, CFG_FILE_EXT, CFG_FILE_INT)
    exit(1)

cfgs = OrderedDict([
    ('common', [
        read_yaml('common', 'BASE', CFG_FILE_INT),
        read_yaml('common', 'BASE', CFG_FILE_EXT),
        read_yaml('common', brand, CFG_FILE_EXT),
    ]),
    ('type', [
        read_yaml(stacktype, 'BASE', CFG_FILE_INT),
        read_yaml(stacktype, 'BASE', CFG_FILE_EXT),
        read_yaml(stacktype, brand, CFG_FILE_EXT),
    ]),
    ('role', cfg_role),
])

RP_base_keys = get_RP_base_keys()

RP = get_RP(cfgs)

try:
    stacktype = RP['cmm']['cmm']['StackType']
except KeyError:
    exit(1)

#    print(RP['dev']['eu-west-1']['CloudFrontCacheBehaviors'][2]['QueryStringCacheKeys'])
if cfg.debug:
    # TO DEBUG - NICELY PRINT NESTED ORDEREDDICT
    show_odict(RP)
    #pprint(RP)

cfg.RP = RP
cfg.RP_cmm = RP['cmm']['cmm']
cfg.stacktype = stacktype
