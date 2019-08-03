import troposphere.logs as lgs

from shared import *

class LogsLogGroup(lgs.LogGroup):
    def __init__(self, title, **kwargs):
        super(LogsLogGroup, self).__init__(title, **kwargs)
        self.LogGroupName = get_final_value('LogGroupName')
        self.RetentionInDays = get_final_value('LogRetentionInDays')


# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class LGS_LogGroup(object):
    def __init__(self, key):
        R_Group = LogsLogGroup('LogsLogGroup')

        cfg.Resources.extend([
            R_Group,
        ])


# Need to stay as last lines
import_modules(globals())
