import sys
import os
import copy
from collections import OrderedDict, Mapping
from pprint import pprint, pformat

import cfg


def get_final_resources(resources):
    resources['final'] = {}

    for r in ['cmm', stacktype, envrole]:
        if r in resources:
            resources['final'].update(resources[r])

    return resources['final']


def mappings_create_entry(mappings, keyenv, keyregion, keyname, keyvalue):
    # create mapping entry
    mappings[keyenv][keyregion].update({keyname: keyvalue})
    # and if present delete the common one, but first record its value
    if keyenv != 'cmm' and keyname in mappings['cmm']['cmm']:
        value = mappings['cmm']['cmm'][keyname]
        del mappings['cmm']['cmm'][keyname]
        # for all real env region that do not already have a key entry i need to create a mapping entry equals to the common one
        # for the non already processed one it could be rewritten later.
        for env in RP_base:
            for region in RP_base[env]:
                if env != 'cmm' and keyname not in mappings[env][region]:
                    mappings[env][region].update({keyname: value})


def get_mapping_env_region(MP, RP, e, r, p):
    mappings = MP

    if isinstance(RP, dict):
        for i, v in RP.iteritems():
            if not e and not r:
                get_mapping_env_region(mappings, v, i, None, None)
            elif not r:
                get_mapping_env_region(mappings, v, e, i, None)
            elif not p:
                get_mapping_env_region(mappings, v, e, r, i)
            else:
                get_mapping_env_region(mappings, v, e, r, str(p) + str(i))
    else:
        if p in mappings['cmm']['cmm'] and RP == mappings['cmm']['cmm'][p]:
            pass
        else:
            mappings_create_entry(mappings, e, r, p, RP)

    return mappings


def get_mappings(RP):
    global mappedvalue

    mappings = {}
    mappings['cmm'] = copy.deepcopy(RP_base)
    mappings['ec2'] = {}
    mappings['resources-env'] = {}

    mappings['cmm'] = get_mapping_env_region(copy.deepcopy(RP_base), RP, None, None, None)

    mappedvalue = mappings['cmm']['cmm']['cmm']
    cfg.mappedvalue = mappedvalue
    # pprint(mappedvalue)

    # delete empy mappings, CloudFormation do not like them!
    for env in RP_base:
        for region in RP_base[env]:
            if len(mappings['cmm'][env][region]) == 0:
                del mappings['cmm'][env][region]
        if len(mappings['cmm'][env]) == 0:
            del mappings['cmm'][env]

    # and remove no more needed cmm one
    if 'cmm' in mappings['cmm']:
        del mappings['cmm']['cmm']

#   #START##MAP INSTANCE TYPE EPHEMERAL####
    map_eph = {
        'InstaceEphemeral0': ['m3.medium', 'm3.large', 'm3.xlarge', 'm3.2xlarge', 'c3.large',
                              'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge', 'g2.2xlarge', 'r3.large', 'r3.xlarge',
                              'r3.2xlarge', 'r3.4xlarge', 'i2.xlarge', 'i2.2xlarge', 'i2.4xlarge',
                              'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge'],
        'InstaceEphemeral1': ['m3.xlarge', 'm3.2xlarge', 'c3.large', 'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge',
                              'i2.2xlarge', 'i2.4xlarge', 'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge'],
        'InstaceEphemeral2': ['i2.4xlarge', 'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge']
    }

    mappings['ec2']['InstanceTypes'] = {}
    instance_list = list(
        set(map_eph['InstaceEphemeral0'] + map_eph['InstaceEphemeral1'] + map_eph['InstaceEphemeral2'])
    )
    for i in instance_list + ['default',
                              't2.nano', 't2.micro', 't2.small', 't2.medium', 't2.large', 't2.xlarge', 't2.2xlarge',
                              't3.nano', 't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
                              'm4.large', 'm4.xlarge', 'm4.2xlarge', 'm4.4xlarge',
                              'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge',
                              'c4.large', 'c4.xlarge', 'c4.2xlarge', 'c4.4xlarge',
                              'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge',
                              'r4.large', 'r4.xlarge', 'r4.2xlarge', 'r4.4xlarge',
                              'r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge',
                              'g3s.xlarge']:
        mappings['ec2']['InstanceTypes'].update({
            i: {
                'InstaceEphemeral0': '1' if i in map_eph['InstaceEphemeral0'] else '0',
                'InstaceEphemeral1': '1' if i in map_eph['InstaceEphemeral1'] else '0',
                'InstaceEphemeral2': '1' if i in map_eph['InstaceEphemeral2'] else '0',
            }
        })

#   #END##MAP INSTANCE TYPE EPHEMERAL####

#  #START##MAP AVABILITY ZONES####
    mappings['resources-env']['AvabilityZones'] = {
        'eu-west-1': {
            'Zone0': 'True',
            'Zone1': 'True',
            'Zone2': 'True'
        },
        'eu-central-1': {
            'Zone0': 'True',
            'Zone1': 'True',
            'Zone2': 'False'
        },
    }
#  #END##MAP AVABILITY ZONES####

    return get_final_resources(mappings)


global envrole
global stacktype
global RP_base
global mappings

envrole = cfg.envrole
stacktype = cfg.stacktype
RP_base = cfg.RP_base

mappings = get_mappings(cfg.RP)

if mappings is not None:
    for m, v in mappings.iteritems():
        cfg.template.add_mapping(m, v)
