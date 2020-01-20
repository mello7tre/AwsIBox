#!/usr/bin/python
from . import cfg
from .shared import stack_add_res
from . import (mappings, lambdas, securitygroup, cloudwatch, loadbalancing, autoscaling, iam,
    codedeploy, route53, crm, events, cloudfront, sqs, sns,
    ecs, ecr, s3, waf, vpc, dynamodb, kms, rds, efs, elasticache,
    servicediscovery, cloudformation, logs, apigateway)


def execute_class(RP_cmm):
    for k, v in cfg.CFG_TO_CLASS.items():
        class_name = v['class']
        module_name = v['module']
        module = globals()[module_name]

        if k in list(RP_cmm.keys()):
            RP_value = RP_cmm[k]
            if isinstance(RP_value, str) and RP_value == 'SkipClass':
                continue
            if isinstance(class_name, list):
                for n in class_name:
                    getattr(module, n)(key=k)
                continue
            stacktype_class = class_name + cfg.stacktype.upper()
            if stacktype_class in dir(module):
                getattr(module, stacktype_class)(key=k)
            elif class_name in dir(module):
                getattr(module, class_name)(key=k)

    stack_add_res()


def generate():
    classenvrole = cfg.envrole.replace('-', '_')  # Ex client-portal -> client_portal
    cfg.classenvrole = classenvrole

    execute_class(cfg.RP_cmm)

    cfg.template.add_description('%s [%s]' % (cfg.envrole, cfg.stacktype))
    cfg.template.add_version('2010-09-09')

    return cfg.template
