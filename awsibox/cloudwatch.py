import troposphere.cloudwatch as clw

from shared import *


class CW_Alarms(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            if not ('Enabled' in v and v['Enabled'] is True):
                continue
            resname = key + str(n)
            # parameters
            p_EvaluationPeriods = Parameter(resname + 'EvaluationPeriods')
            p_EvaluationPeriods.Description = 'Number of periods for alarm evaluation - 0 to disable - empty for default based on env/role'
            p_EvaluationPeriods.AllowedValues = ['', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

            p_Period = Parameter(resname + 'Period')
            p_Period.Description = 'Period lenght in seconds (multiple of 60) - empty for default based on env/role'
            p_Period.AllowedValues = ['', '60', '120', '180', '240', '300']

            p_Threshold = Parameter(resname + 'Threshold')
            p_Threshold.Description = 'Threshold for alarm triggering - empty for default based on env/role'
            p_Threshold.AllowedValues = ['', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60', '65', '70', '75', '80', '85', '90', '95', '100']

            cfg.Parameters.extend([
                p_EvaluationPeriods,
                #p_Period,
                p_Threshold,
            ])

            # conditions
            do_no_override(True)
            c_Alarm = { resname: Or(
                And(
                    Condition(resname + 'EvaluationPeriodsOverride'),
                    Not(Equals(Ref(resname + 'EvaluationPeriods'), '0')),
                ),
                And(
                    Not(Condition(resname + 'EvaluationPeriodsOverride')),
                    Not(Equals(get_final_value(resname + 'EvaluationPeriods'), '0')),
                )
            )}
            do_no_override(False)

            cfg.Conditions.append(c_Alarm)

            # resources
            r_Alarm = clw.Alarm(resname)
            auto_get_props(r_Alarm, v, recurse=True)
            if hasattr(r_Alarm, 'Metrics'):
                r_Alarm.Period = Ref('AWS::NoValue')
            if not hasattr(r_Alarm, 'Condition'):
                r_Alarm.Condition = resname

            cfg.Resources.append(r_Alarm)

            # outputs
            o_Alarm = Output(resname)
            o_Alarm.Value = get_sub_mapex(
                'Period=${1M},EvaluationPeriods=${2M},Threshold=${3M}',
                [
                    resname + 'Period',
                    resname + 'EvaluationPeriods',
                    resname + 'Threshold'
                ]
            )

            cfg.Outputs.append(o_Alarm)


# Need to stay as last lines
import_modules(globals())
