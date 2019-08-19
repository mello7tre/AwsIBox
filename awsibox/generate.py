#!/usr/bin/python
import cfg
from shared import stack_add_res, import_modules

def execute_class(RP_cmm):
    import_modules(globals())

    for k, v in cfg.CFG_TO_CLASS.iteritems():
        if k in RP_cmm.keys():
            RP_value = RP_cmm[k]
            if isinstance(RP_value, str) and RP_value == 'SkipClass':
                continue
            if isinstance(v, list):
                for n in v:
                    globals()[n](key=k)
                continue
            stacktype_class = v + cfg.stacktype.upper()
            if stacktype_class in globals():
                globals()[stacktype_class](key=k)
            elif v in globals():
                globals()[v](key=k)

    stack_add_res()


def generate():
    classenvrole = cfg.envrole.replace('-', '_')  # Ex client-portal -> client_portal
    cfg.classenvrole = classenvrole

    execute_class(cfg.RP_cmm)

    cfg.template.add_description('%s [%s]' % (cfg.envrole, cfg.stacktype))
    cfg.template.add_version('2010-09-09')

    return cfg.template
