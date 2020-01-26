import troposphere.cloudwatch as clw

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class CW_Alarms(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            if not ('Enabled' in v and v['Enabled'] is True):
                continue
            resname = f'{key}{n}'
            # parameters
            p_EvaluationPeriods = Parameter(f'{resname}EvaluationPeriods')
            p_EvaluationPeriods.Description = (
                'Number of periods for alarm evaluation - 0 to disable - '
                'empty for default based on env/role')
            p_EvaluationPeriods.AllowedValues = [
                '', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

            p_Period = Parameter(f'{resname}Period')
            p_Period.Description = (
                'Period lenght in seconds (multiple of 60) - '
                'empty for default based on env/role')
            p_Period.AllowedValues = ['', '60', '120', '180', '240', '300']

            p_Threshold = Parameter(f'{resname}Threshold')
            p_Threshold.Description = (
                'Threshold for alarm triggering - '
                'empty for default based on env/role')
            p_Threshold.AllowedValues = [
                '', '10', '15', '20', '25', '30', '35', '40', '45', '50',
                '55', '60', '65', '70', '75', '80', '85', '90', '95', '100']

            add_obj([
                p_EvaluationPeriods,
                # p_Period,
                p_Threshold,
            ])

            # conditions
            c_EvaluationPeriods = get_condition(
                resname, 'not_equals', '0', f'{resname}EvaluationPeriods')

            add_obj(c_EvaluationPeriods)

            # resources
            r_Alarm = clw.Alarm(resname)
            auto_get_props(r_Alarm, v, recurse=True)
            if hasattr(r_Alarm, 'Metrics'):
                r_Alarm.Period = Ref('AWS::NoValue')
            if not hasattr(r_Alarm, 'Condition'):
                r_Alarm.Condition = resname

            add_obj(r_Alarm)

            # outputs
            o_Alarm = Output(resname)
            o_Alarm.Value = get_subvalue(
                'Period=${1M},EvaluationPeriods=${2M},Threshold=${3M}',
                [
                    f'{resname}Period',
                    f'{resname}EvaluationPeriods',
                    f'{resname}Threshold'
                ]
            )

            add_obj(o_Alarm)
