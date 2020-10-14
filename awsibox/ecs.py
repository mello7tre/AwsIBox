import troposphere.ecs as ecs

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .securitygroup import (SecurityGroupEcsService,
                            SecurityGroupRuleEcsService, SG_SecurityGroupsECS)


class ECSService(ecs.Service):
    def __init__(self, title, scheme, **kwargs):
        super().__init__(title, **kwargs)

        self.Cluster = get_expvalue('Cluster', 'ClusterStack')

        # DAEMON MODE DO NOT SUPPORT DESIRED OR PLACEMENT STRATEGIES,
        # IS SIMPLY ONE TASK FOR CONTAINER INSTANCE
        if cfg.SchedulingStrategy == 'REPLICA':
            self.DesiredCount = get_endvalue('CapacityDesired')
            self.DeploymentConfiguration = ecs.DeploymentConfiguration(
                MaximumPercent=get_endvalue(
                    'DeploymentConfigurationMaximumPercent'),
                MinimumHealthyPercent=get_endvalue(
                    'DeploymentConfigurationMinimumHealthyPercent'),
            )
            self.PlacementStrategies = If(
                'LaunchTypeFarGate',
                Ref('AWS::NoValue'),
                [
                    # ecs.PlacementStrategy(
                    #    Type='spread',
                    #    Field='attribute:ecs.availability-zone'
                    # ),
                    ecs.PlacementStrategy(
                        Type='spread',
                        Field='instanceId'
                    )
                ]
            )
        elif cfg.SchedulingStrategy == 'DAEMON':
            self.SchedulingStrategy = 'DAEMON'

        self.LaunchType = get_endvalue('LaunchType')

        if cfg.HealthCheckGracePeriodSeconds != 0:
            self.HealthCheckGracePeriodSeconds = (
                get_endvalue('HealthCheckGracePeriodSeconds'))

        # self.PlatformVersion = 'LATEST'

        if cfg.LoadBalancerApplication:
            self.LoadBalancers = []
            self.Role = If(
                'NetworkModeAwsVpc',
                Ref('AWS::NoValue'),
                get_expvalue('RoleECSService')
            )
            # When creating a service that specifies multiple target groups,
            # the Amazon ECS service-linked role must be created.
            # The role is created by omitting the Role property
            # in AWS CloudFormation
            if (cfg.LoadBalancerApplicationExternal and
                    cfg.LoadBalancerApplicationInternal):
                self.Role = Ref('AWS::NoValue')

        self.TaskDefinition = Ref('TaskDefinition')


class ECSTaskDefinition(ecs.TaskDefinition):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.ExecutionRoleArn = If(
            'LaunchTypeFarGate',
            get_expvalue('RoleECSTaskExecution'),
            Ref('AWS::NoValue')
        )
        self.TaskRoleArn = Ref('RoleTask')

        self.Cpu = If(
            'CpuTask',
            get_endvalue('Cpu'),
            Ref('AWS::NoValue')
        )

        self.Memory = If(
            'LaunchTypeFarGate',
            get_endvalue('Memory'),
            Ref('AWS::NoValue')
        )

        self.NetworkMode = If(
            'NetworkModeAwsVpc',
            'awsvpc',
            get_endvalue('NetworkMode'),
        )

        self.RequiresCompatibilities = If(
            'LaunchTypeFarGate',
            ['EC2', 'FARGATE'],
            ['EC2']
        )


# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################


class ECSEnvironment(ecs.Environment):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title
        valuename = f'{name}Value'
        self.Name = get_endvalue(f'{name}Name')
        self.Value = get_endvalue(valuename)


class ECSMountPoint(ecs.MountPoint):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        self.ReadOnly = False
        self.SourceVolume = self.title
        self.ContainerPath = key['ContainerPath']


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
        auto_get_props(self, key, recurse=True)

        self.Essential = True

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

        self.LogConfiguration = If(
            'LogConfiguration',
            ecs.LogConfiguration(
                LogDriver=get_endvalue('LogDriver'),
                Options={
                    # 'awslogs-group': get_endvalue('AwsLogsGroup'),
                    # 'awslogs-create-group': True,
                    'awslogs-group': Ref('LogsLogGroup'),
                    'awslogs-region': Ref('AWS::Region'),
                    'awslogs-stream-prefix': Ref('AWS::StackName')
                }
            ),
            Ref('AWS::NoValue')
        )

        if 'MountPoints' in key:
            self.MountPoints = [
                ECSMountPoint(n, key=k) for n, k in key['MountPoints'].items()
            ]

        if 'Name' in key:
            self.Name = get_subvalue('${EnvRole}-${1M}', f'{name}Name')
        else:
            self.Name = Ref('EnvRole')

        if 'ContainerPort' in key:
            PortMapping = ecs.PortMapping()
            auto_get_props(PortMapping, key, mapname=self.title)
            if 'HostPort' not in key:
                PortMapping.HostPort = If(
                    'NetworkModeAwsVpc',
                    get_endvalue(f'{name}ContainerPort'),
                    0
                )
            self.PortMappings = [PortMapping]


class ECSVolume(ecs.Volume):
    def __init__(self, title, key, **kwargs):
        super(ECSVolume, self).__init__(title, **kwargs)
        self.Name = self.title
        self.Host = ecs.Host(
            SourcePath=key['SourcePath']
        )


class ECSNetworkConfiguration(ecs.NetworkConfiguration):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.AwsvpcConfiguration = ecs.AwsvpcConfiguration(
            SecurityGroups=[
                GetAtt('SecurityGroupEcsService', 'GroupId')
                ] + SG_SecurityGroupsECS().SecurityGroups,
            Subnets=Split(',', get_expvalue('SubnetsPrivate'))
        )


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


class ECS_TaskDefinition(object):
    def __init__(self, key):
        Environments_Base = [
            ecs.Environment(
                Name='EnvRegion',
                Value=Ref('AWS::Region')
            ),
            ecs.Environment(
                Name='Env',
                Value=Ref('Env')
            ),
            ecs.Environment(
                Name='EnvAbbr',
                Value=Ref('EnvShort')
            ),
            ecs.Environment(
                Name='EnvBrand',
                Value=cfg.BrandDomain
            ),
            ecs.Environment(
                Name='EnvRole',
                Value=Ref('EnvRole')
            ),
            ecs.Environment(
                Name='EnvStackName',
                Value=Ref('AWS::StackName')
            ),
            ecs.Environment(
                Name='EnvClusterStackName',
                Value=get_endvalue('ClusterStack')
            ),
        ]

        Containers = []
        for n, v in cfg.ContainerDefinitions.items():
            Environments = []
            MountPoints = []

            name = f'ContainerDefinitions{n}'  # Ex. ContainerDefinitions1

            # parameters

            # if ContainerDefinitions have RepoName
            # use different EnvApp version
            if n == 1 or 'RepoName' in v:
                nameenvapp = f'EnvApp{n}Version'  # Ex. EnvApp1Version

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

            # outputs
            EnvValue_Out_String = []
            EnvValue_Out_Map = {}
            if 'Envs' in v:
                for m, w in v['Envs'].items():
                    envname = f'{name}Envs{m}'
                    envkeyname = w['Name']
                    # parameters
                    EnvValue = Parameter(f'{envname}Value')
                    EnvValue.Description = (
                        f'{envkeyname} - empty for default based on env/role')

                    # If key NoParam is present skip adding Parameters
                    # (usefull as they have a limited max number)
                    if 'NoParam' not in w:
                        add_obj(EnvValue)

                    Environment = ECSEnvironment(envname, key=w)
                    Environments.append(Environment)

                    # outputs
                    EnvValue_Out_String.append(
                        '%s=${%s}' % (envkeyname, envkeyname))
                    EnvValue_Out_Map.update({
                        envkeyname: Environment.Value
                    })

            o_EnvValueOut = Output(f'{name}Envs')
            o_EnvValueOut.Value = Sub(
                ','.join(EnvValue_Out_String), **EnvValue_Out_Map)

            add_obj(o_EnvValueOut)

            Environments.extend(Environments_Base)

            # parameters
            if 'Cpu' in v:
                p_Cpu = Parameter(f'{name}Cpu')
                p_Cpu.Description = (
                    'Cpu Share for containers - '
                    'empty for default based on env/role')

                add_obj(p_Cpu)

            if 'Memory' in v:
                p_Memory = Parameter(f'{name}Memory')
                p_Memory.Description = (
                    'Memory hard limit for containers - '
                    'empty for default based on env/role')

                add_obj(p_Memory)

            if 'MemoryReservation' in v:
                p_MemoryReservation = Parameter(f'{name}MemoryReservation')
                p_MemoryReservation.Description = (
                    'Memory soft limit for containers - '
                    'empty for default based on env/role')

                add_obj(p_MemoryReservation)

            if 'Command' in v:
                p_Command = Parameter(f'{name}Command')
                p_Command.Description = 'Command to execute'
                p_Command.Type = 'CommaDelimitedList'

                add_obj(p_Command)

            Container = ECSContainerDefinition(name, key=v, index=n)
            Container.Environment = Environments

            # Trick to force reload of Service using parameter
            Container.DockerLabels = If(
                'DockerLabelLastUpdateOverride',
                {'LastUpdate': Ref('DockerLabelLastUpdate')},
                Ref('AWS::NoValue'),
            )

            Containers.append(Container)

            # outputs
            Constraints_Out_String = []
            Constraints_Out_Map = {}

            if 'Cpu' in v:
                Constraints_Out_String.append(
                    'Cpu:${Cpu}')
                Constraints_Out_Map.update({
                    'Cpu': Container.Cpu
                })

            if 'Memory' in v:
                Constraints_Out_String.append(
                    'Memory:${Memory}')
                Constraints_Out_Map.update({
                    'Memory': Container.Memory
                })

            if 'MemoryReservation' in v:
                Constraints_Out_String.append(
                    'MemoryReservation:${MemoryReservation}')
                Constraints_Out_Map.update({
                    'MemoryReservation': Container.MemoryReservation
                })

            if Constraints_Out_String:
                o_Constraints = Output(f'{name}Constraints')
                o_Constraints.Value = Sub(
                    ','.join(Constraints_Out_String), **Constraints_Out_Map)

                add_obj(o_Constraints)

            if 'Command' in v:
                o_Command = Output(f'{name}Command')
                o_Command.Value = Join(',', get_endvalue(f'{name}Command'))

                add_obj(o_Command)

        # Resources
        R_TaskDefinition = ECSTaskDefinition('TaskDefinition')
        R_TaskDefinition.ContainerDefinitions = Containers

        if cfg.Volumes:
            Volumes = []
            for n, v in cfg.Volumes.items():
                Volume = ECSVolume(n, key=v)
                Volumes.append(Volume)

            R_TaskDefinition.Volumes = Volumes

        add_obj([
            R_TaskDefinition,
        ])


class ECS_Service(object):
    def __init__(self, key):
        # Resources
        R_SG = SecurityGroupEcsService('SecurityGroupEcsService')

        R_Service = ECSService('Service', scheme='')

        if cfg.LoadBalancerApplicationExternal:
            R_Service.LoadBalancers.append(
                ECSLoadBalancer('', scheme='External'))

            SGRule = SecurityGroupRuleEcsService(scheme='External')
            R_SG.SecurityGroupIngress.append(SGRule)

        if cfg.LoadBalancerApplicationInternal:
            R_Service.LoadBalancers.append(
                ECSLoadBalancer('', scheme='Internal'))

            SGRule = SecurityGroupRuleEcsService(scheme='Internal')
            R_SG.SecurityGroupIngress.append(SGRule)

        R_Service.NetworkConfiguration = If(
            'NetworkModeAwsVpc',
            ECSNetworkConfiguration(''),
            Ref('AWS::NoValue'))

        add_obj([
            R_Service,
            R_SG,
        ])


class ECS_Cluster(object):
    def __init__(self, key):
        # Resources
        R_Cluster = ecs.Cluster('Cluster')

        add_obj([
            R_Cluster,
        ])
