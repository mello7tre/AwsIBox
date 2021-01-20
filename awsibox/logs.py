import troposphere.logs as lgs

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


class LogsLogGroup(lgs.LogGroup):
    def __init__(self, title, **kwargs):
        super(LogsLogGroup, self).__init__(title, **kwargs)
        self.LogGroupName = get_endvalue('LogGroupName')
        self.RetentionInDays = get_endvalue('LogRetentionInDays')


def LGS_LogGroup(key):
    R_Group = LogsLogGroup('LogsLogGroup')

    add_obj([
        R_Group])
