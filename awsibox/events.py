import troposphere.events as eve

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionEvent
from .securitygroup import SG_SecurityGroupsECS


class EVEEcsParameters(eve.EcsParameters):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.LaunchType = get_endvalue('LaunchType')
        self.NetworkConfiguration = eve.NetworkConfiguration(
            AwsVpcConfiguration=eve.AwsVpcConfiguration(
                SecurityGroups=SG_SecurityGroupsECS().SecurityGroups,
                Subnets=Split(',', get_expvalue('SubnetsPrivate'))))
        self.TaskDefinitionArn = Ref('TaskDefinition')


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class EVE_EventRules(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'
            # parameters
            p_State = Parameter(f'{resname}State')
            p_State.Description = (
                'Events Rule State - empty for default based on env/role')
            p_State.AllowedValues = ['', 'DISABLED', 'ENABLED']

            if 'ScheduleExpression' in v:
                p_ScheduleExpression = Parameter(
                    f'{resname}ScheduleExpression')
                p_ScheduleExpression.Description = (
                    'Events Rule Schedule - '
                    'empty for default based on env/role')

                add_obj(p_ScheduleExpression)

            add_obj([
                p_State,
            ])

            # resources
            Targets = []
            need_ecsEventsRole = None
            for m, w in v['Targets'].items():
                targetname = f'{resname}Targets{m}'
                Target = eve.Target('')

                if m.startswith('Lambda'):
                    permname = '%s%s' % (
                        m.replace('Lambda', 'LambdaPermission'), resname)
                    r_LambdaPermission = LambdaPermissionEvent(
                        permname, key=w, source=resname)
                    if 'Condition' in v:
                        r_LambdaPermission.Condition = v['Condition']

                    add_obj(r_LambdaPermission)
                if m.startswith('ECSCluster'):
                    props = {
                        'Arn': get_subvalue(
                            'arn:aws:ecs:${AWS::Region}:${AWS::AccountId}:'
                            'cluster/${1E}', 'Cluster', stack='ClusterStack'),
                        'EcsParameters': EVEEcsParameters(''),
                        'RoleArn': GetAtt('RoleTask', 'Arn'),
                        'Id': f'Target{m}',
                    }
                    need_ecsEventsRole = True

                    # add common "fixed" props
                    auto_get_props(Target, props, rootdict=props,
                                   mapname='', del_prefix=targetname)

                # add props found in yaml cfg
                auto_get_props(Target, w, mapname=targetname, recurse=True)
                Targets.append(Target)

            r_Rule = eve.Rule(resname)
            auto_get_props(r_Rule, v)
            r_Rule.Name = Sub('${AWS::StackName}-${EnvRole}-' f'Rule{n}')
            r_Rule.Targets = Targets

            # if target is Ecs Task add RoleArn
            if need_ecsEventsRole:
                r_Rule.RoleArn = Sub(
                    'arn:aws:iam::${AWS::AccountId}:role/ecsEventsRole')

            add_obj(r_Rule)

            # outputs
            o_State = Output(f'{resname}State')
            o_State.Value = get_endvalue(f'{resname}State')

            if 'ScheduleExpression' in v:
                o_ScheduleExpression = Output(
                    f'{resname}ScheduleExpression')
                o_ScheduleExpression.Value = get_endvalue(
                    f'{resname}ScheduleExpression')

                add_obj(o_ScheduleExpression)

            add_obj([
                o_State,
            ])
