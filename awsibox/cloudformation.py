from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj, auto_build_obj)


class CFM_Parameters(object):
    def __init__(self, key):
        auto_build_obj(Parameter(''), getattr(cfg, key))


class CFM_Conditions(object):
    def __init__(self, key):
        do_no_override(True)
        for n, v in getattr(cfg, key).items():
            c_Condition = {n: eval(v)}

            add_obj(c_Condition)
        do_no_override(False)


class CFM_Mappings(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            c_Mapping = {n: v}

            cfg.Mappings.update(c_Mapping)


class CFM_Outputs(object):
    def __init__(self, key):
        auto_build_obj(Output(''), getattr(cfg, key))
