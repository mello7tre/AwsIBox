import troposphere.awslambda as lbd

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    import_lambda,
    parse_ibox_key,
)


class LambdaPermission(lbd.Permission):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = "lambda:InvokeFunction"


class LambdaPermissionEvent(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "events.amazonaws.com"
        self.FunctionName = eval(key["Arn"])
        self.SourceArn = GetAtt(source, "Arn")


class LambdaPermissionS3(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "s3.amazonaws.com"
        self.FunctionName = key
        self.SourceArn = Sub("arn:aws:s3:::%s" % source)
