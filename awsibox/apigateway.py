import troposphere.apigateway as agw
import troposphere.route53 as r53

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionApiGateway
from .iam import IAMPolicyApiGatewayPrivate


class ApiGatewayAccount(agw.Account):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CloudWatchRoleArn = get_expvalue('RoleApiGatewayCloudWatch')


class ApiGatewayResource(agw.Resource):
    def __init__(self, title, key, stage, **kwargs):
        super().__init__(title, **kwargs)
        mapname = f'ApiGatewayStage{stage}ApiGatewayResource'

        auto_get_props(self)
        self.RestApiId = Ref('ApiGatewayRestApi')

        # if stage override ApiGatewayResource specs, get it
        try:
            getattr(cfg, mapname)
        except Exception:
            pass
        else:
            auto_get_props(self, mapname)


class ApiGatewayMethod(agw.Method):
    def __init__(self, title, key, basename, name, stage, **kwargs):
        super().__init__(title, **kwargs)
        mapname = (f'ApiGatewayStage{stage}'
                   f'ApiGatewayResource{basename}Method{name}')

        try:
            getattr(cfg, mapname)
        except Exception:
            pass
        else:
            auto_get_props(self, mapname)

        auto_get_props(self)
        self.RestApiId = Ref('ApiGatewayRestApi')
        self.ResourceId = Ref(f'ApiGatewayResource{basename}')

        # If Uri is a lambda self.Integration.Uri will be like:
        # 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaName.Arn}/invocations'
        # i need to append stage version (Ex. v1) to the Lambda Name so that
        # ${LambdaName.Arn} -> ${LambdaNameV1.Arn}
        if ':lambda:' in self.Integration.Uri:
            iu = self.Integration.Uri
            dot_found = iu.rfind('.')
            before_dot = iu[0:dot_found]
            after_dot = iu[dot_found:]
            if after_dot.startswith('.Arn'):
                self.Integration.Uri = Sub(f'{before_dot}{stage}{after_dot}')


class ApiGatewayStage(agw.Stage):
    def __init__(self, title, name, key, **kwargs):
        super().__init__(title, **kwargs)
        self.StageName = name

        auto_get_props(self)

        self.RestApiId = Ref('ApiGatewayRestApi')
        self.DeploymentId = Ref(f'ApiGatewayDeployment{name}')
        self.DeploymentId = If(
            f'Deployment{name}A',
            Ref(f'ApiGatewayDeployment{name}A'),
            Ref(f'ApiGatewayDeployment{name}B'),
        )


class ApiGatewayDeployment(agw.Deployment):
    def __init__(self, title, name, key, **kwargs):
        super().__init__(title, **kwargs)
        lastresource = next(reversed(list(cfg.ApiGatewayResource)))
        lastmethod = (next(
            reversed(list(cfg.ApiGatewayResource[lastresource]['Method']))))
        self.DependsOn = f'ApiGatewayResource{lastresource}Method{lastmethod}'
        self.Description = Ref(f'Deployment{name}Description')
        self.RestApiId = Ref('ApiGatewayRestApi')


def AGW_Account(key):
    # Resources
    R_Account = ApiGatewayAccount('ApiGatewayAccount')

    add_obj([
        R_Account])


def AGW_DomainName(key):
    for n, v in getattr(cfg, key).items():
        if not v['IBOXENABLED']:
            continue

        resname = f'{key}{n}'
        # resources
        r_Domain = agw.DomainName(resname)
        auto_get_props(r_Domain)

        r_r53 = r53.RecordSetType(resname)
        if 'REGIONAL' in v['EndpointConfiguration']['Types']:
            auto_get_props(r_r53, 'R53RecordSetApiGatewayDomainNameRegional')
        else:
            auto_get_props(r_r53, 'R53RecordSetApiGatewayDomainNameGlobal')
        r_r53.title = f'RecordSet{resname}'

        # outputs
        o_Domain = Output(resname)
        o_Domain.Value = Ref(resname)
        o_Domain.Export = Export(resname)

        add_obj([
            r_Domain,
            r_r53,
            o_Domain])


def AGW_BasePathMapping(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_Path = agw.BasePathMapping(resname)
        auto_get_props(r_Path)

        add_obj(r_Path)


def AGW_UsagePlans(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        for m, w in v['ApiStages'].items():
            # parameters
            p_Stage = Parameter(f'{resname}ApiStages{m}Stage')
            p_Stage.Description = (
                f'{m} Stage - empty for default based on env/role')

            add_obj(p_Stage)

        # resources
        r_UsagePlan = agw.UsagePlan(resname)
        auto_get_props(r_UsagePlan)

        # outputs
        o_UsagePlan = Output(resname)
        o_UsagePlan.Value = Ref(resname)
        o_UsagePlan.Export = Export(resname)

        add_obj([
            r_UsagePlan,
            o_UsagePlan])


def AGW_ApiKeys(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        # parameters
        p_Enabled = Parameter(f'{resname}Enabled')
        p_Enabled.Description = (
            f'{resname}Enabled - empty for default based on env/role')

        p_UsagePlan = Parameter(f'{resname}UsagePlan')
        p_UsagePlan.Description = (
            f'{resname}UsagePlan - empty for default based on env/role')

        add_obj([
            p_Enabled,
            p_UsagePlan])

        # resources
        r_ApiKey = agw.ApiKey(resname)
        auto_get_props(r_ApiKey)

        if 'UsagePlan' in v:
            plankey_name = f'{resname}UsagePlan'
            r_UsagePlanKey = agw.UsagePlanKey(f'ApiGatewayUsagePlan{n}')
            r_UsagePlanKey.KeyId = Ref(resname)
            r_UsagePlanKey.KeyType = 'API_KEY'
            r_UsagePlanKey.UsagePlanId = ImportValue(
                get_subvalue(
                    'ApiGatewayUsagePlan${1M}', f'{resname}UsagePlan')
            )

            add_obj(r_UsagePlanKey)

        # outputs
        o_ApiKey = Output(resname)
        o_ApiKey.Value = Ref(resname)

        add_obj([
            r_ApiKey,
            o_ApiKey])


def AGW_Stages(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        depname = f'Deployment{n}'
        # parameters
        p_DeploymentDescription = Parameter(f'{depname}Description')
        p_DeploymentDescription.Description = f'{depname} Description'
        p_DeploymentDescription.Default = n

        p_Deployment = Parameter(depname)
        p_Deployment.Description = (
            f'{depname} - change between A/B '
            'to trigger new deploy')
        p_Deployment.AllowedValues = ['A', 'B']
        p_Deployment.Default = 'A'

        add_obj([
            p_DeploymentDescription,
            p_Deployment])

        # conditons
        c_DeploymentA = get_condition(
            f'{depname}A', 'equals', 'A', depname, nomap=True)

        c_DeploymentB = get_condition(
            f'{depname}B', 'equals', 'B', depname, nomap=True)

        add_obj([
            c_DeploymentA,
            c_DeploymentB])

        # resources
        r_Stage = ApiGatewayStage(resname, name=n, key=v)

        r_DeploymentA = ApiGatewayDeployment(f'ApiGatewayDeployment{n}A',
                                             name=n, key=v)
        r_DeploymentA.Condition = f'{depname}A'

        r_DeploymentB = ApiGatewayDeployment(f'ApiGatewayDeployment{n}B',
                                             name=n, key=v)
        r_DeploymentB.Condition = f'{depname}B'

        # output
        o_Deployment = Output(depname)
        o_Deployment.Value = Ref(depname)

        add_obj([
            r_Stage,
            r_DeploymentA,
            r_DeploymentB,
            o_Deployment])


def AGW_RestApi(key):
    # Resources
    R_RestApi = agw.RestApi('ApiGatewayRestApi')
    auto_get_props(R_RestApi, f'{key}Base')
    R_RestApi.Policy = IAMPolicyApiGatewayPrivate()

    try:
        condition = cfg.PolicyCondition
        R_RestApi.Policy['Statement'][0]['Condition'] = condition
    except Exception:
        pass

    add_obj([
        R_RestApi,
    ])

    for n, v in cfg.ApiGatewayResource.items():
        resname = f'ApiGatewayResource{n}'
        agw_stage = cfg.ApiGatewayRestApi['Base']['Stage']
        r_Resource = ApiGatewayResource(resname, key=v, stage=agw_stage)

        for m, w in v['Method'].items():
            r_Method = ApiGatewayMethod(f'{resname}Method{m}',
                                        key=w, basename=n,
                                        name=m, stage=agw_stage)

            add_obj([
                r_Resource,
                r_Method])

    for n, v in cfg.Lambda.items():
        r_LambdaPermission = LambdaPermissionApiGateway(
            f'LambdaPermission{n}', name=Ref(f'Lambda{n}'),
            source=Sub('arn:aws:execute-api:${AWS::Region}:'
                       '${AWS::AccountId}:${ApiGatewayRestApi}/*/*/*')
        )

        add_obj(r_LambdaPermission)
