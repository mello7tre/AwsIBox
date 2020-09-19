import sys
import os
import copy
from pprint import pprint, pformat

from . import cfg


def mappings_create_entry(mappings, keyenv, keyregion, keyname, keyvalue):
    global mappedvalues

    # create mapping entry
    mappings[keyenv][keyregion].update({keyname: keyvalue})
    if keyenv != 'cmm':
        mappedvalues.add(keyname)
    # and if present delete the common one, but first record its value
    if keyenv != 'cmm' and keyname in mappings['cmm']['cmm']:
        value = mappings['cmm']['cmm'][keyname]
        del mappings['cmm']['cmm'][keyname]
        # for all real env region that do not already have a key entry
        # i need to create a mapping entry equals to the common one
        # for the non already processed one it could be rewritten later.
        for env in cfg.RP_base:
            for region in cfg.RP_base[env]:
                if env != 'cmm' and keyname not in mappings[env][region]:
                    mappings[env][region].update({keyname: value})


def get_mapping_env_region(MP, RP, e, r, p):
    mappings = MP

    if isinstance(RP, dict):
        for i, v in RP.items():
            if not e and not r:
                get_mapping_env_region(mappings, v, i, None, None)
            elif not r:
                get_mapping_env_region(mappings, v, e, i, None)
            elif not p:
                get_mapping_env_region(mappings, v, e, r, i)
            else:
                get_mapping_env_region(mappings, v, e, r, f'{p}{i}')
    else:
        if p in mappings['cmm']['cmm'] and RP == mappings['cmm']['cmm'][p]:
            pass
        else:
            mappings_create_entry(mappings, e, r, p, RP)

    return mappings


def get_envregion_mapping():
    global mappedvalues
    mappedvalues = set()

    mappings = get_mapping_env_region(
        copy.deepcopy(cfg.RP_base), cfg.RP, None, None, None)
    fixedvalues = mappings['cmm']['cmm']
    cfg.fixedvalues = fixedvalues
    cfg.mappedvalues = mappedvalues

    if cfg.debug:
        print('##########FIXEDVALUES#########START#####')
        pprint(cfg.fixedvalues)
        print('##########FIXEDVALUES#########END#######')

        print('##########MAPPEDVALUES#########START#####')
        pprint(cfg.mappedvalues)
        print('##########MAPPEDVALUES#########END#######')

    # delete empy mappings, CloudFormation do not like them!
    for env in cfg.RP_base:
        for region in cfg.RP_base[env]:
            if len(mappings[env][region]) == 0:
                del mappings[env][region]
        if len(mappings[env]) == 0:
            del mappings[env]

    # and remove no more needed cmm one
    if 'cmm' in mappings:
        del mappings['cmm']

    return mappings


def get_ec2_mapping():
    mappings = {}

#   #START##MAP INSTANCE TYPE EPHEMERAL####
    map_eph = {
        'InstaceEphemeral0': [
            'm3.medium', 'm3.large', 'm3.xlarge', 'm3.2xlarge', 'c3.large',
            'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge',
            'g2.2xlarge', 'r3.large', 'r3.xlarge',
            'r3.2xlarge', 'r3.4xlarge', 'i2.xlarge', 'i2.2xlarge',
            'i2.4xlarge', 'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge',
        ],
        'InstaceEphemeral1': [
            'm3.xlarge', 'm3.2xlarge',
            'c3.large', 'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge',
            'i2.2xlarge', 'i2.4xlarge', 'd2.xlarge', 'd2.2xlarge',
            'd2.4xlarge',
        ],
        'InstaceEphemeral2': [
            'i2.4xlarge', 'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge',
        ]
    }

    mappings['InstanceTypes'] = {}

    for i in cfg.INSTANCE_LIST:
        mappings['InstanceTypes'].update({
            i: {
                'InstaceEphemeral0': '1' if i in map_eph['InstaceEphemeral0']
                else '0',
                'InstaceEphemeral1': '1' if i in map_eph['InstaceEphemeral1']
                else '0',
                'InstaceEphemeral2': '1' if i in map_eph['InstaceEphemeral2']
                else '0',
            }
        })
#   #END##MAP INSTANCE TYPE EPHEMERAL####

    return mappings


def get_azones_mapping():
    mappings = {}
    mappings['AvabilityZones'] = {}
    AZ = cfg.AZones

    for r in cfg.regions:
        zones = {}
        try:
            nzones = AZ[r]
        except Exception:
            nzones = AZ['default']

        try:
            nzones = cfg.RP['dev'][r]['AZones']
        except Exception:
            pass

        for n in range(AZ['MAX']):
            zones[f'Zone{n}'] = 'True' if nzones > n else 'False'

        mappings['AvabilityZones'][r] = zones

    return mappings


class Mappings(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            if n == 'EnvRegion':
                mapping = get_envregion_mapping()
            if n == 'EC2':
                mapping = get_ec2_mapping()
            if n == 'AZones':
                mapping = get_azones_mapping()

            cfg.Mappings.update(mapping)
