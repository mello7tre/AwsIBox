import troposphere.events as eve

from shared import *


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
        for n, v in RP_cmm[key].iteritems():
            resname = key + n  # Ex. EventsRuleElasticSearchSnapShot
            # parameters
            p_State = Parameter(resname + 'State')
            p_State.Description = 'Events Rule State - empty for default based on env/role'
            p_State.AllowedValues = ['', 'DISABLED', 'ENABLED']

            if 'ScheduleExpression' in v:
                p_ScheduleExpression = Parameter(resname + 'ScheduleExpression')
                p_ScheduleExpression.Description = 'Events Rule Schedule - empty for default based on env/role'

                cfg.Parameters.append(p_ScheduleExpression)

            cfg.Parameters.extend([
                p_State,
            ])

            # resources
            Targets = []
            for m, w in v['Targets'].iteritems():
                targetname = resname + 'Targets' + m
                Target = EVETarget('')
                Target.setup(name=targetname, key=w)
                Targets.append(Target)

                if m.startswith('Lambda'):
                    permname = m.replace('Lambda', 'LambdaPermission') + resname  # Ex. LambdaPermissionElasticSearchSnapShotEventsElasticsearchSnapShot
                    r_LambdaPermission = LambdaPermissionEvent(permname)
                    r_LambdaPermission.setup(key=w, source=resname)

                    cfg.Resources.append(r_LambdaPermission)

            r_Rule = EVERule(resname)
            r_Rule.setup(key=v, name=n)
            r_Rule.Targets = Targets

            cfg.Resources.append(r_Rule)

            # outputs
            o_State = Output(resname + 'State')
            o_State.Value = get_final_value(resname + 'State')
   
            if 'ScheduleExpression' in v:
                o_ScheduleExpression = Output(resname + 'ScheduleExpression')
                o_ScheduleExpression.Value = get_final_value(resname + 'ScheduleExpression')

                cfg.Outputs.append(o_ScheduleExpression)
    
            cfg.Outputs.extend([
                o_State,
            ])


# Need to stay as last lines
import_modules(globals())
