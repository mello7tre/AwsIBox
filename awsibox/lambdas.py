import troposphere.awslambda as lbd

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj, import_lambda)
from .iam import IAMRoleLambdaBase

class LambdaPermission(lbd.Permission):
    def setup(self):
        self.Action = 'lambda:InvokeFunction'


class LambdaPermissionEvent(LambdaPermission):
    def setup(self, key, source):
        super(LambdaPermissionEvent, self).setup()
        self.Principal = 'events.amazonaws.com'
        self.FunctionName = eval(key['Arn'])
        self.SourceArn = GetAtt(source, 'Arn')


class LambdaPermissionS3(LambdaPermission):
    def setup(self, key, source):
        super(LambdaPermissionS3, self).setup()
        self.Principal = 's3.amazonaws.com'
        self.FunctionName = key
        self.SourceArn = Sub('arn:aws:s3:::%s' % getattr(cfg, source))


class LambdaPermissionSNS(LambdaPermission):
    def setup(self, key, **kwargs):
        super(LambdaPermissionSNS, self).setup(**kwargs)
        auto_get_props(self, key)
        self.Principal = 'sns.amazonaws.com'
        self.FunctionName = eval(key['Endpoint'])
        self.SourceArn = eval(key['TopicArn'])


class LambdaPermissionApiGateway(LambdaPermission):
    def setup(self, name, source):
        super(LambdaPermissionApiGateway, self).setup()
        self.Principal = 'apigateway.amazonaws.com'
        self.FunctionName = name
        self.SourceArn = source


class LambdaPermissionLoadBalancing(LambdaPermission):
    def setup(self, name):
        super(LambdaPermissionLoadBalancing, self).setup()
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
            self.Code = lbd.Code(
                ZipFile=Join('', import_lambda(import_name))
            )
        auto_get_props(self, key, recurse=True)
        self.FunctionName = Sub('${AWS::StackName}-${EnvRole}-' + name)
        if 'Handler' not in key:
            self.Handler = 'index.lambda_handler'
        self.Role = GetAtt('RoleLambda' + name, 'Arn')

        if all(k in key for k in ['SecurityGroupIds', 'SubnetIds']):
            self.VpcConfig = lbd.VPCConfig('')
            auto_get_props(self.VpcConfig, key, mapname=self.title)

        if 'Variables' in key:
            self.Environment = lbd.Environment(
                Variables={
                    varname: get_endvalue(self.title + 'Variables' + varname) for varname in key['Variables']
                }
            )


class LambdaLayerVersionPermission(lbd.LayerVersionPermission):
    def __init__(self, title, **kwargs):
        super(LambdaLayerVersionPermission, self).__init__(title, **kwargs)
        self.Action = 'lambda:GetLayerVersion'
        self.Principal = Ref('AWS::AccountId')


def LambdaLayers(obj, resname, i):
    layername = '%s%s' % (resname, i)
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

class LBD_Lambdas(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n

            try: v['Code']['S3Key']
            except: pass
            else:
                s3keyname = resname + 'Code' + 'S3Key'
                # parameters
                p_S3Key = Parameter(s3keyname)
                p_S3Key.Description = 'S3Key Name for lambda %s Code' % n

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
                add_obj(get_condition(resname, 'not_equals', 'None', resname + 'Enabled'))

                r_Lambda.Condition = resname

            if 'Layers' in v:
                r_Lambda.Layers = []
                for i, j in enumerate(v['Layers']):
                    r_Lambda.Layers.append(
                        LambdaLayers(r_Lambda, '%s%s' % (resname, 'Layers'), i)
                    )

            if 'Version' in v:
                versionname = resname + 'Version'
                # parameters
                p_Version = Parameter(versionname)
                p_Version.Description = 'LambdaVersion change between A/B to force deploy new version'
                p_Version.AllowedValues = ['', 'A', 'B']
                p_Version.Default = ''

                add_obj(p_Version)

                # conditons
                add_obj([
                    {versionname + 'A': Equals(
                        Ref(resname + 'Version'), 'A'
                    )},
                    {versionname + 'B': Equals(
                        Ref(resname + 'Version'), 'B'
                    )},
                    {versionname: Or(
                        Condition(versionname + 'A'),
                        Condition(versionname + 'B'),
                    )},
                ])

                # resources
                r_VersionA = LambdaVersion(versionname + 'A', name=resname )
                r_VersionA.Condition = versionname + 'A'
                
                r_VersionB = LambdaVersion(versionname + 'B', name=resname )
                r_VersionB.Condition = versionname + 'B'

                add_obj([
                    r_VersionA,
                    r_VersionB,
                ])

                # outputs
                o_Version = Output(versionname)
                o_Version.Value = If(
                    versionname + 'A',
                    Ref(versionname + 'A'),
                    Ref(versionname + 'B')
                )
                o_Version.Condition = versionname
                
                add_obj([
                    o_Version,
                ])

            # Automatically setup a lambda Role with base permissions.
            r_Role = IAMRoleLambdaBase('Role' + resname)
            r_Role.setup(key=v)
            if hasattr(r_Lambda, 'Condition'):
            	r_Role.Condition = r_Lambda.Condition

            add_obj([
                r_Lambda,
                r_Role,
            ])

            if 'Export' in v and v['Export']:
                O_Lambda = Output(resname)
                O_Lambda.Value = GetAtt(resname, 'Arn')
                O_Lambda.Export = Export(resname)

                add_obj(O_Lambda)


class LBD_LayerVersions(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n

            try: v['Content']['S3Key']
            except: pass
            else:
                s3keyname = resname + 'Content' + 'S3Key'
                # parameters
                p_S3Key = Parameter(s3keyname)
                p_S3Key.Description = 'S3Key Name for lambda %s Content' % n

                add_obj(p_S3Key)

                # outputs
                o_S3Key = Output(s3keyname)
                o_S3Key.Value = get_endvalue(s3keyname)

                add_obj(o_S3Key)

            # resources
            r_Layer = lbd.LayerVersion(resname)
            auto_get_props(r_Layer, v, recurse=True)
            r_LayerPermission = LambdaLayerVersionPermission('LambdaLayerPermission' + n)
            r_LayerPermission.LayerVersionArn = Ref(resname)

            add_obj([
                r_Layer,
                r_LayerPermission,
            ])

            # output
            o_Layer = Output(resname)
            o_Layer.Value = Ref(resname)

            add_obj(o_Layer)


class LBD_Permissions(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n

            # resources
            r_Permission = LambdaPermission(resname)
            r_Permission.setup()
            auto_get_props(r_Permission, v, recurse=True)

            add_obj([
                r_Permission,
            ])


class LBD_EventSourceMappings(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n

            # resources
            r_EventSourceMapping = lbd.EventSourceMapping(resname)
            auto_get_props(r_EventSourceMapping, v, recurse=True)

            add_obj([
                r_EventSourceMapping,
            ])
