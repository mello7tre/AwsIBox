import troposphere.ecs as ecs

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .securitygroup import (SecurityGroupEcsService,
                            SecurityGroupRuleEcsService)


class ECSLoadBalancer(ecs.LoadBalancer):
    def __init__(self, title, scheme, **kwargs):
        super().__init__(title, **kwargs)
        self.ContainerName = Ref('EnvRole')
        self.ContainerPort = get_endvalue('ContainerDefinitions1ContainerPort')
        self.TargetGroupArn = Ref(f'TargetGroup{scheme}')


class ECSContainerDefinition(ecs.ContainerDefinition):
    def __init__(self, title, key, index, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. ContainerDefinitions1
        auto_get_props(self)

        if len(cfg.ContainerDefinitions) == 1:
            self.Cpu = If(
                'CpuTask',
                get_endvalue('Cpu'),
                get_endvalue(f'{name}Cpu')
            )
            self.Memory = If(
                'LaunchTypeFarGate',
                get_endvalue('Memory'),
                get_endvalue(f'{name}Memory')
            )

        if 'RepoName' in key:
            self.Image = get_subvalue(
                '${1M}.dkr.ecr.${AWS::Region}.amazonaws.com/${2M}:'
                '${EnvApp%sVersion}' % index,
                ['EcrAccount', f'{name}RepoName']
            )
        # use the same EnvApp version for all containers
        elif cfg.RepoName != 'None':
            self.Image = get_subvalue(
                '${1M}.dkr.ecr.${AWS::Region}.amazonaws.com/${2M}:'
                '${EnvApp1Version}',
                ['EcrAccount', 'RepoName']
            )
        elif cfg.Image != 'None':
            self.Image = get_endvalue('Image')

        if 'Name' in key:
            self.Name = get_subvalue('${EnvRole}-${1M}', f'{name}Name')
        else:
            self.Name = Ref('EnvRole')


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

def ECS_ContainerDefinition():
    Containers = []
    for n, v in cfg.ContainerDefinitions.items():
        Environments = []
        MountPoints = []

        name = f'ContainerDefinitions{n}'  # Ex. ContainerDefinitions1

        # if ContainerDefinitions have RepoName
        # use different EnvApp version
        if n == 1 or 'RepoName' in v:
            nameenvapp = f'EnvApp{n}Version'  # Ex. EnvApp1Version

            # parameters
            EnvApp = Parameter(nameenvapp)
            EnvApp.Description = nameenvapp
            EnvApp.AllowedPattern = '^[a-zA-Z0-9-_.]*$'
            EnvApp.Default = '1'

            add_obj(EnvApp)

            # outputs
            o_EnvAppOut = Output(nameenvapp)
            o_EnvAppOut.Value = Ref(nameenvapp)

            # and use different output for RepoName
            if cfg.RepoName != 'None':
                if 'RepoName' in v:
                    o_Repo = Output(f'{name}RepoName')
                    o_Repo.Value = get_endvalue(f'{name}RepoName')
                else:
                    o_Repo = Output('RepoName')
                    o_Repo.Value = get_endvalue('RepoName')

                add_obj(o_Repo)

            add_obj([
                o_EnvAppOut,
            ])

        # resources
        Container = ECSContainerDefinition(name, key=v, index=n)
        Containers.append(Container)

        # outputs
        EnvValue_Out_String = []
        EnvValue_Out_Map = {}
        for m, w in v['Environment'].items():
            if m.startswith('Env'):
                continue
            envname = f'{name}Environment{m}'
            envkeyname = w['Name']
            # parameters
            p_EnvValue = Parameter(f'{envname}Value')
            p_EnvValue.Description = (
                f'{envkeyname} - empty for default based on env/role')

            # If key NoParam is present skip adding Parameters
            # (usefull as they have a limited max number)
            if 'NoParam' not in w:
                add_obj(p_EnvValue)

            # outputs
            EnvValue_Out_String.append(
                '%s=${%s}' % (envkeyname, envkeyname))
            EnvValue_Out_Map.update({
                envkeyname: get_endvalue(f'{envname}Value')
            })

        o_EnvValueOut = Output(f'{name}Environment')
        o_EnvValueOut.Value = Sub(
            ','.join(EnvValue_Out_String), **EnvValue_Out_Map)

        add_obj(o_EnvValueOut)

    return Containers


def ECS_TaskDefinition(key):
    # Resources
    R_TaskDefinition = ecs.TaskDefinition('TaskDefinitionBase')
    auto_get_props(R_TaskDefinition)
    R_TaskDefinition.ContainerDefinitions = ECS_ContainerDefinition()

    add_obj([
        R_TaskDefinition])


def ECS_Service(key):
    # Resources
    R_SG = SecurityGroupEcsService('SecurityGroupEcsService')
    if cfg.LoadBalancerApplicationExternal:
        SGRule = SecurityGroupRuleEcsService(scheme='External')
        R_SG.SecurityGroupIngress.append(SGRule)

    if cfg.LoadBalancerApplicationInternal:
        SGRule = SecurityGroupRuleEcsService(scheme='Internal')
        R_SG.SecurityGroupIngress.append(SGRule)

    add_obj(R_SG)

    for n, v in getattr(cfg, key).items():
        if not v['IBOXENABLED']:
            continue
        mapname = f'{key}{n}'

        # trick to avoid changing, for now, current service resource name
        if n == 'Spot':
            resname = 'ServiceSpot'
        else:
            resname = 'Service'

        r_Service = ecs.Service(mapname)
        auto_get_props(r_Service)
        r_Service.title = resname

        if cfg.LoadBalancerApplication:
            r_Service.LoadBalancers = []
            r_Service.Role = If(
                'NetworkModeAwsVpc',
                Ref('AWS::NoValue'),
                get_expvalue('RoleECSService'))

        # When creating a service that specifies multiple target groups,
        # the Amazon ECS service-linked role must be created.
        # The role is created by omitting the Role property
        # in AWS CloudFormation
        if (cfg.LoadBalancerApplicationExternal and
                cfg.LoadBalancerApplicationInternal):
            r_Service.Role = Ref('AWS::NoValue')

        if cfg.LoadBalancerApplicationExternal:
            r_Service.LoadBalancers.append(
                ECSLoadBalancer('', scheme='External'))

        if cfg.LoadBalancerApplicationInternal:
            r_Service.LoadBalancers.append(
                ECSLoadBalancer('', scheme='Internal'))

        add_obj(r_Service)


def ECS_Cluster(key):
    # Resources
    R_Cluster = ecs.Cluster('Cluster')

    add_obj([
        R_Cluster,
    ])
