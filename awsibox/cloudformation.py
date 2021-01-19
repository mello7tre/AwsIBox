import troposphere.cloudformation as cfm

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj,
                     auto_build_obj)


def CFM_Parameters(key):
    auto_build_obj(Parameter(''), getattr(cfg, key))


def CFM_Conditions(key):
    do_no_override(True)
    for n, v in getattr(cfg, key).items():
        c_Condition = {n: eval(v)}

        add_obj(c_Condition)
    do_no_override(False)


def CFM_Mappings(key):
    for n, v in getattr(cfg, key).items():
        c_Mapping = {n: v}

        cfg.Mappings.update(c_Mapping)


def CFM_Outputs(key):
    auto_build_obj(Output(''), getattr(cfg, key))


def CFM_CustomResourceReplicator(key):
    resname = 'CloudFormationCustomResourceStackReplicator'
    # Parameters
    P_ReplicateRegions = Parameter('CCRReplicateRegions')
    P_ReplicateRegions.Description = (
        'Regions where to replicate - None to disable - '
        'empty for default based on env/role')
    P_ReplicateRegions.Type = 'CommaDelimitedList'

    add_obj(P_ReplicateRegions)

    # Resources
    R_Replicator = cfm.CustomResource(resname)

    if 'LambdaCCRStackReplicator' in cfg.Resources:
        R_Replicator.DependsOn = 'IAMPolicyLambdaCCRStackReplicator'
        R_Replicator.ServiceToken = GetAtt('LambdaCCRStackReplicator', 'Arn')
    else:
        R_Replicator.ServiceToken = get_expvalue('LambdaCCRStackReplicator')

    for p, v in cfg.Parameters.items():
        if not p.startswith('Env'):
            value = get_endvalue(p)
        else:
            value = Ref(p)
        setattr(R_Replicator, p, value)

    add_obj(R_Replicator)


def CFM_CustomResourceLightHouse(key):
    resname = 'CloudFormationCustomResourceLightHouse'
    # Parameters
    P_LightHouse = Parameter('CCRLightHouse')
    P_LightHouse.Description = (
        'Enable CustomResource for LightHouse - None to disable - '
        'empty for default based on env/role')

    add_obj(P_LightHouse)

    # Conditions
    C_LightHouse = get_condition(
        resname, 'not_equals', 'None', 'CCRLightHouse')

    add_obj(C_LightHouse)

    # Resources
    R_LightHouse = cfm.CustomResource(resname)
    R_LightHouse.Condition = resname
    R_LightHouse.DependsOn = 'Service'
    R_LightHouse.ServiceToken = get_expvalue('LambdaCCRLightHouse')
    R_LightHouse.EnvRole = Ref('EnvRole')
    R_LightHouse.EnvApp1Version = Ref('EnvApp1Version')
    R_LightHouse.RepoName = get_endvalue('RepoName')

    add_obj(R_LightHouse)


def CFM_CustomResourceFargateSpot(key):
    resname = 'CloudFormationCustomResourceFargateSpot'
    R_FargateSpot = cfm.CustomResource(resname)
    R_FargateSpot.Condition = 'FargateSpot'
    R_FargateSpot.DependsOn = 'ServiceSpot'
    R_FargateSpot.ServiceToken = get_expvalue('LambdaCCRFargateSpot')
    R_FargateSpot.ServiceArn = Ref('ServiceSpot')
    R_FargateSpot.ServiceBase = GetAtt('Service', 'Name')
    R_FargateSpot.ServiceSpot = GetAtt('ServiceSpot', 'Name')
    R_FargateSpot.Cluster = get_expvalue('Cluster', 'ClusterStack')
    R_FargateSpot.ScalingPolicy = Ref('ApplicationAutoScalingScalingPolicyCpu')

    add_obj(R_FargateSpot)
