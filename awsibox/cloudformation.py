from shared import *


class CFM_Parameters(object):
    def __init__(self, key):
        auto_build_obj(Parameter(''), RP_cmm[key], obj_list=cfg.Parameters)


class CFM_Conditions(object):
    def __init__(self, key):
        do_no_override(True)
        for n, v in RP_cmm[key].iteritems():
            c_Condition = {n: eval(v)}

            cfg.Conditions.append(c_Condition)
        do_no_override(False)


class CFM_Outputs(object):
    def __init__(self, key):
        auto_build_obj(Output(''), RP_cmm[key], obj_list=cfg.Outputs)

# Need to stay as last lines
import_modules(globals())
