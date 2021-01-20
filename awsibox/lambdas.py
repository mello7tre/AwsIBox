import troposphere.awslambda as lbd

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj, import_lambda)
from .iam import IAMRoleLambdaBase


class LambdaPermission(lbd.Permission):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = 'lambda:InvokeFunction'


class LambdaPermissionEvent(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = 'events.amazonaws.com'
        self.FunctionName = eval(key['Arn'])
        self.SourceArn = GetAtt(source, 'Arn')


class LambdaPermissionS3(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = 's3.amazonaws.com'
        self.FunctionName = key
        self.SourceArn = Sub('arn:aws:s3:::%s' % getattr(cfg, source))


class LambdaPermissionSNS(LambdaPermission):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = 'sns.amazonaws.com'
        self.FunctionName = eval(key['Endpoint'])
        self.SourceArn = eval(key['TopicArn'])


class LambdaPermissionApiGateway(LambdaPermission):
    def __init__(self, title, name, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = 'apigateway.amazonaws.com'
        self.FunctionName = name
        self.SourceArn = source


class LambdaPermissionLoadBalancing(LambdaPermission):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = 'elasticloadbalancing.amazonaws.com'
        self.FunctionName = name


class LambdaVersion(lbd.Version):
    def __init__(self, title, name, **kwargs):
        super(LambdaVersion, self).__init__(title, **kwargs)
        self.FunctionName = Ref(name)


class LambdaFunction(lbd.Function):
    def setup(self, key, name):
        import_name = key['ImportName'] if 'ImportName' in key else name
        if 'Code' not in key:
            self.Code = lbd.Code()
            try:
                self.Code.ZipFile = Join('', import_lambda(import_name))
            except Exception:
                self.Code.ZipFile = (
                    'print("Use Code parameter in yaml '
                    f'or create file lib/lambas/{import_name}.code '
                    'with lambda code to execute.")')
        auto_get_props(self)
        self.FunctionName = Sub('${AWS::StackName}-${EnvRole}-%s' % name)
        if 'Handler' not in key:
            self.Handler = 'index.lambda_handler'
        try:
            getattr(self, 'Role')
        except Exception:
            self.Role = GetAtt(f'RoleLambda{name}', 'Arn')

        if all(k in key for k in ['SecurityGroupIds', 'SubnetIds']):
            self.VpcConfig = lbd.VPCConfig('')
            auto_get_props(self.VpcConfig, self.title)

        # Variables - skip if atEdge - always set Env, EnvRole
        try:
            key['AtEdge']
        except Exception as e:
            self.Environment = lbd.Environment(
                Variables={
                    'Env': Ref('EnvShort'),
                    'EnvRole': Ref('EnvRole'),
                }
            )
            if 'Variables' in key:
                self.Environment.Variables.update({
                    varname: get_endvalue(f'{self.title}Variables{varname}')
                    for varname in key['Variables']
                })


class LambdaLayerVersionPermission(lbd.LayerVersionPermission):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = 'lambda:GetLayerVersion'
        self.Principal = Ref('AWS::AccountId')


def LambdaLayers(obj, resname, i):
    layername = f'{resname}{i}'
    # parameters
    p_Layer = Parameter(layername)
    p_Layer.Description = layername

    add_obj(p_Layer)

    # condition
    add_obj(
        get_condition(layername, 'not_equals', '', mapinlist=(resname, i))
    )

    # output
    o_Layer = Output(layername)
    o_Layer.Value = Select(i, get_endvalue(resname, condition=layername))
    o_Layer.Value = get_endvalue(resname, condition=layername, mapinlist=i)

    return o_Layer.Value

##


def LBD_Lambdas(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        try:
            v['Code']['S3Key']
        except Exception:
            pass
        else:
            s3keyname = f'{resname}CodeS3Key'
            # parameters
            p_S3Key = Parameter(s3keyname)
            p_S3Key.Description = f'S3Key Name for lambda {n} Code'

            add_obj(p_S3Key)

            # outputs
            o_S3Key = Output(s3keyname)
            o_S3Key.Value = get_endvalue(s3keyname)

            add_obj(o_S3Key)

        # resources
        r_Lambda = LambdaFunction(resname)
        r_Lambda.setup(key=v, name=n)

        if 'Enabled' in v:
            # conditions
            add_obj(get_condition(
                resname, 'not_equals', 'None', f'{resname}Enabled'))

            r_Lambda.Condition = resname

        if 'Layers' in v:
            r_Lambda.Layers = []
            for i, j in enumerate(v['Layers']):
                r_Lambda.Layers.append(
                    LambdaLayers(
                        r_Lambda, '%s%s' % (resname, 'Layers'), i)
                )

        if 'Version' in v:
            versionname = f'{resname}Version'
            versionnameA = f'{versionname}A'
            versionnameB = f'{versionname}B'

            # parameters
            p_Version = Parameter(versionname)
            p_Version.Description = (
                'LambdaVersion - change between A/B '
                'to force deploy new version')
            p_Version.AllowedValues = ['', 'A', 'B']
            p_Version.Default = ''

            add_obj(p_Version)

            # conditons
            c_VersionA = {versionnameA: And(
                Condition(resname),
                get_condition(
                    '', 'equals', 'A', versionname, nomap=True),
            )}

            c_VersionB = {versionnameB: And(
                Condition(resname),
                get_condition(
                    '', 'equals', 'B', versionname, nomap=True),
            )}

            c_Version = {versionname: Or(
                Condition(versionnameA),
                Condition(versionnameB),
            )}

            add_obj([
                c_VersionA,
                c_VersionB,
                c_Version])

            # resources
            r_VersionA = LambdaVersion(versionnameA, name=resname)
            r_VersionA.Condition = versionnameA

            r_VersionB = LambdaVersion(versionnameB, name=resname)
            r_VersionB.Condition = versionnameB

            # outputs
            o_Version = Output(versionname)
            o_Version.Value = If(
                versionnameA,
                Ref(versionnameA),
                Ref(versionnameB)
            )
            o_Version.Condition = versionname

            add_obj([
                r_VersionA,
                r_VersionB,
                o_Version])

        if not v.get('SkipRole'):
            # Automatically setup a lambda Role with base permissions.
            r_Role = IAMRoleLambdaBase(f'Role{resname}', key=v)
            if hasattr(r_Lambda, 'Condition'):
                r_Role.Condition = r_Lambda.Condition
            add_obj(r_Role)

        add_obj(r_Lambda)

        if v.get('Export'):
            O_Lambda = Output(resname)
            O_Lambda.Value = GetAtt(resname, 'Arn')
            O_Lambda.Export = Export(resname)

            add_obj(O_Lambda)


def LBD_LayerVersions(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        try:
            v['Content']['S3Key']
        except Exception:
            pass
        else:
            s3keyname = f'{resname}ContentS3Key'
            # parameters
            p_S3Key = Parameter(s3keyname)
            p_S3Key.Description = f'S3Key Name for lambda {n} Content'

            add_obj(p_S3Key)

            # outputs
            o_S3Key = Output(s3keyname)
            o_S3Key.Value = get_endvalue(s3keyname)

            add_obj(o_S3Key)

        # resources
        r_Layer = lbd.LayerVersion(resname)
        auto_get_props(r_Layer)
        r_LayerPermission = LambdaLayerVersionPermission(
            f'LambdaLayerPermission{n}')
        r_LayerPermission.LayerVersionArn = Ref(resname)

        # output
        o_Layer = Output(resname)
        o_Layer.Value = Ref(resname)

        add_obj([
            r_Layer,
            r_LayerPermission,
            o_Layer])


def LBD_Permissions(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_Permission = LambdaPermission(resname)
        auto_get_props(r_Permission)

        add_obj([
            r_Permission])


def LBD_EventSourceMappings(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_EventSourceMapping = lbd.EventSourceMapping(resname)
        auto_get_props(r_EventSourceMapping)

        add_obj([
            r_EventSourceMapping])


def LBD_EventInvokeConfig(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_EventInvokeConfig = lbd.EventInvokeConfig(resname)
        auto_get_props(r_EventInvokeConfig)

        add_obj([
            r_EventInvokeConfig])
