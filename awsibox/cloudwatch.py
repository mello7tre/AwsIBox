import troposphere.cloudwatch as clw

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


def CW_Alarms(key):
    for n, v in getattr(cfg, key).items():
        # be carefull that value is enabled in loadbalancing too
        if not v['IBOXENABLED']:
            continue
        resname = f'{key}{n}'
        # resources
        r_Alarm = clw.Alarm(resname)
        auto_get_props(r_Alarm)
        if hasattr(r_Alarm, 'Metrics'):
            r_Alarm.Period = Ref('AWS::NoValue')

        add_obj(r_Alarm)
