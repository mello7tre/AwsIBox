import troposphere.certificatemanager as crm

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class CRM_Certificate(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            if not v['IBOXENABLED']:
                continue
            # resources
            resname = f'{key}{n}'
            r_Certificate = crm.Certificate(resname)
            auto_get_props(r_Certificate)
            r_Certificate.Tags = Tags(Name=n)

            add_obj([
                r_Certificate,
            ])

            # outputs
            o_Certificate = Output(resname)
            o_Certificate.Value = Ref(resname)

            if hasattr(r_Certificate, 'Condition'):
                o_Certificate.Condition = r_Certificate.Condition

            add_obj([
                o_Certificate,
            ])


class CRM_CertificateEC2(object):
    def __init__(self, key):
        if cfg.ListenerLoadBalancerHttpsPort != 'None':
            CRM_Certificate(key)


class CRM_CertificateECS(object):
    def __init__(self, key):
        if cfg.ListenerLoadBalancerHttpsPort != 443:
            CRM_Certificate(key)


class CRM_CertificateRES(object):
    def __init__(self, key):
        CRM_Certificate(key)
