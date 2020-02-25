import troposphere.cloudformation as clf

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class CLF_CustomResourceReplicator(object):
    def __init__(self, key):
        # Parameters
        P_ReplicateRegions = Parameter('ReplicateRegions')
        P_ReplicateRegions.Description = (
            'Regions where to replicate - None to disable - '
            'empty for default based on env/role')
        P_ReplicateRegions.Type = 'CommaDelimitedList'

        add_obj(P_ReplicateRegions)

        # Resources
        R_Replicator = clf.CustomResource(
            'CloudFormationCustomResourceStackReplicator')

        if 'LambdaStackReplicator' in cfg.Resources:
            R_Replicator.ServiceToken = GetAtt('LambdaStackReplicator', 'Arn')
        else:
            R_Replicator.ServiceToken = get_expvalue('LambdaStackReplicator')

        for p, v in cfg.Parameters.items():
            if not p.startswith('Env'):
                value = get_endvalue(p)
            else:
                value = Ref(p)
            setattr(R_Replicator, p, value)

        add_obj(R_Replicator)
