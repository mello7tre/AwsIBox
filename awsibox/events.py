import troposphere.events as eve

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionEvent

class EVERule(eve.Rule):
    def setup(self, key, name):
        auto_get_props(self, key)
        self.Name = Sub('${AWS::StackName}-${EnvRole}-' + 'Rule' + name)


class EVETarget(eve.Target):
    def setup(self, name, key):
        auto_get_props(self, key, mapname=name)

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class EVE_EventRules(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. EventsRuleElasticSearchSnapShot
            # parameters
            p_State = Parameter(resname + 'State')
            p_State.Description = 'Events Rule State - empty for default based on env/role'
            p_State.AllowedValues = ['', 'DISABLED', 'ENABLED']

            if 'ScheduleExpression' in v:
                p_ScheduleExpression = Parameter(resname + 'ScheduleExpression')
                p_ScheduleExpression.Description = 'Events Rule Schedule - empty for default based on env/role'

                add_obj(p_ScheduleExpression)

            add_obj([
                p_State,
            ])

            # resources
            Targets = []
            for m, w in v['Targets'].items():
                targetname = resname + 'Targets' + m
                Target = EVETarget('')
                Target.setup(name=targetname, key=w)
                Targets.append(Target)

                if m.startswith('Lambda'):
                    permname = m.replace('Lambda', 'LambdaPermission') + resname  # Ex. LambdaPermissionElasticSearchSnapShotEventsElasticsearchSnapShot
                    r_LambdaPermission = LambdaPermissionEvent(permname)
                    r_LambdaPermission.setup(key=w, source=resname)

                    add_obj(r_LambdaPermission)

            r_Rule = EVERule(resname)
            r_Rule.setup(key=v, name=n)
            r_Rule.Targets = Targets

            add_obj(r_Rule)

            # outputs
            o_State = Output(resname + 'State')
            o_State.Value = get_endvalue(resname + 'State')
   
            if 'ScheduleExpression' in v:
                o_ScheduleExpression = Output(resname + 'ScheduleExpression')
                o_ScheduleExpression.Value = get_endvalue(resname + 'ScheduleExpression')

                add_obj(o_ScheduleExpression)
    
            add_obj([
                o_State,
            ])
