#!/usr/bin/python
import sys
import os

parent_dir_name = os.getcwd()
sys.path.append(parent_dir_name + '/lib')

import awsibox.cfg as cfg
from awsibox.args import *
from awsibox.RP import *
from awsibox.mapping import *
from awsibox.shared import *

stacktype = cfg.stacktype
envrole = cfg.envrole


def execute_class():
    for k, v in cfg.CFG_TO_CLASS.iteritems():
        if k in RP_cmm.keys():
            RP_value = RP_cmm[k]
            if isinstance(RP_value, str) and RP_value == 'SkipClass':
                continue
            if isinstance(v, list):
                for n in v:
                    globals()[n](key=k)
                continue
            if v + stacktype.upper() in globals():
                globals()[v + stacktype.upper()](key=k)
            elif v in globals():
                globals()[v](key=k)

    stack_add_res()


# ################################
# #### END STACK ROLE CLASSES ####
# ################################

classenvrole = envrole.replace('-', '_')  # Ex client-portal -> client_portal
cfg.classenvrole = classenvrole

execute_class()

cfg.template.add_description(envrole + ' [' + stacktype + ']')
cfg.template.add_version('2010-09-09')

print(cfg.template.to_json())
# print(cfg.template.to_yaml())
