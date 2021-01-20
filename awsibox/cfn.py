import troposphere.cloudformation as cfm

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


def cfn_ecs_cluster():
    init_args = {}

    init_args.update({
        'REPOSITORIES': cfm.InitConfig(
            commands=If('GPUInstance', {
                '10-epel-repo': {
                    'command': 'amazon-linux-extras install -y epel',
                    'test': '! test -e /etc/yum.repos.d/epel.repo'
                },
                # 'cuda-repo': {
                #    'command': 'yum install -y '
                #    'http://developer.download.nvidia.com'
                #    '/compute/cuda/repos/rhel7/x86_64/'
                #    'cuda-repo-rhel7-10.0.130-1.x86_64.rpm',
                #    'test': 'test ! -e /etc/yum.repos.d/cuda.repo'
                # },
                'nvidia-docker': {
                    'command': 'curl -s -L '
                    'https://nvidia.github.io'
                    '/nvidia-docker/amzn2/nvidia-docker.repo | '
                    'tee /etc/yum.repos.d/nvidia-docker.repo',
                    'test': 'test ! -e /etc/yum.repos.d/nvidia-docker.repo'
                },
            }, Ref('AWS::NoValue')),
            files=If('GPUInstance', {
                '/etc/yum.repos.d/epel-nvidia.repo': {
                    'content': Join('\n', [
                        '[epel-nvidia]',
                        'name=negativo17 - Nvidia',
                        'baseurl=https://negativo17.org'
                        '/repos/nvidia/epel-7/$basearch/',
                        'enabled=1',
                        'skip_if_unavailable=1',
                        'gpgcheck=1',
                        'gpgkey=https://negativo17.org'
                        '/repos/RPM-GPG-KEY-slaanesh',
                        'enabled_metadata=1',
                        'metadata_expire=6h',
                        'type=rpm-md',
                        'repo_gpgcheck=0'
                    ])
                }
            }, Ref('AWS::NoValue'))
        ),
        'PACKAGES': cfm.InitConfig(
            packages={
                'yum': {
                    'nfs-utils': [],
                    'make': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'automake': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'gcc': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'gcc-c++': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'kernel-devel': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    # 'cuda': If('GPUInstance', [], Ref('AWS::NoValue')),
                    'dkms-nvidia': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'nvidia-driver-cuda': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                    'nvidia-docker2': If(
                        'GPUInstance', [], Ref('AWS::NoValue')),
                }
            }
        ),
        'SERVICES': cfm.InitConfig(
            files={
                '/etc/ecs/ecs.config': {
                    'content': Join('\n', [
                        Sub('ECS_CLUSTER=${Cluster}'),
                        If(
                            'GPUInstance',
                            'ECS_DISABLE_PRIVILEGED=false',
                            Ref('AWS::NoValue')
                        ),
                    ])
                },
                '/etc/docker/daemon.json': If('GPUInstance', {
                    'content': Join('\n', [
                        '{',
                        '  "default-runtime": "nvidia",',
                        '  "runtimes": {',
                        '    "nvidia": {',
                        '      "path": "/usr/bin/nvidia-container-runtime",',
                        '      "runtimeArgs": []',
                        '    }',
                        '  }',
                        '}',
                    ])
                }, Ref('AWS::NoValue'))
            },
            commands={
                '01-kern-modules': If('GPUInstance', {
                    'command': 'rmmod nvidia_modeset;rmmod nvidia_uvm;'
                    'rmmod nvidia;modprobe nvidia;modprobe nvidia_uvm;true'
                }, Ref('AWS::NoValue')),
                '02-restart-docker': If('GPUInstance', {
                    'command': 'pkill -SIGHUP dockerd'
                }, Ref('AWS::NoValue')),
            }
        )
    })

    # aws ecs ami by default run postfix, use yaml cfg Postfix: false to
    # stop it
    try:
        if cfg.Postfix == 'false':
            postfixService = {'postfix': {
                'enabled': 'false',
                'ensureRunning': cfg.Postfix,
            }}
            dataIf = init_args['SERVICES'].services.data['Fn::If']
            dataIf[1]['sysvinit'].update(postfixService)
            dataIf[2] = {'sysvinit': postfixService}
    except Exception:
        pass

    return init_args
