import troposphere.events as eve

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionEvent


class EVERule(eve.Rule):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self, key)
        self.Name = Sub('${AWS::StackName}-${EnvRole}-' f'Rule{name}')


class EVETarget(eve.Target):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self, key, mapname=name)

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
            for m, w in v['Targets'].items():
                targetname = f'{resname}Targets{m}'
                Target = EVETarget('', name=targetname, key=w)
                Targets.append(Target)

                if m.startswith('Lambda'):
                    permname = '%s%s' % (
                        m.replace('Lambda', 'LambdaPermission'), resname)
                    r_LambdaPermission = LambdaPermissionEvent(
                        permname, key=w, source=resname)
                    if 'Condition' in v:
                        r_LambdaPermission.Condition = v['Condition']

                    add_obj(r_LambdaPermission)

            r_Rule = EVERule(resname, key=v, name=n)
            r_Rule.Targets = Targets

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
