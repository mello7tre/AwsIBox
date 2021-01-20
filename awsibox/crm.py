import troposphere.certificatemanager as crm

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


def CRM_Certificate(key):
    for n, v in getattr(cfg, key).items():
        if not v['IBOXENABLED']:
            continue
        # resources
        resname = f'{key}{n}'
        r_Certificate = crm.Certificate(resname)
        auto_get_props(r_Certificate)
        r_Certificate.Tags = Tags(Name=n)

        # outputs
        o_Certificate = Output(resname)
        o_Certificate.Value = Ref(resname)

        if hasattr(r_Certificate, 'Condition'):
            o_Certificate.Condition = r_Certificate.Condition

        add_obj([
            r_Certificate,
            o_Certificate])


def CRM_CertificateEC2(key):
    if cfg.ListenerLoadBalancerHttpsPort != 'None':
        CRM_Certificate(key)


def CRM_CertificateECS(key):
    if cfg.ListenerLoadBalancerHttpsPort != 443:
        CRM_Certificate(key)


def CRM_CertificateRES(key):
    CRM_Certificate(key)
