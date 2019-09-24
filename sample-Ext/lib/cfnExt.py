import troposphere.cloudformation as cfm

from awsibox.common import *
from awsibox.shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props)
import awsibox.cfg

def cfn_elasticsearch():
    init_args = {}

    init_args.update({
        'REPOSITORIES': cfm.InitConfig(
            files={
                '/etc/yum.repos.d/elasticsearch.repo': {
                    'content': Join('', [
                        '[elasticsearch-6.x]\n',
                        'name=Elasticsearch repository for 6.x packages\n',
                        'baseurl=https://artifacts.elastic.co/packages/6.x/yum\n',
                        'gpgcheck=1\n',
                        'gpgkey=https://artifacts.elastic.co/GPG-KEY-elasticsearch\n',
                        'enabled=1\n'
                    ])
                }
            },
            commands={
                '10_epel-repo': {
                    'command': 'yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm',
                    'test': '! test -e /etc/yum.repos.d/epel.repo'
                },
                '20_elastic.co-signature': {
                    'command': 'rpm --import https://artifacts.elastic.co/GPG-KEY-elasticsearch',
                    'test': '! rpm -qi gpg-pubkey-d88e42b4-52371eca'
                },
                '40_repo-set-options': {
                    'command': 'yum-config-manager --save --setopt=\*.skip_if_unavailable=1'
                },
            }
        ),
        'PACKAGES': cfm.InitConfig(
            packages={
                'yum': {
                    'elasticsearch': [],
                    'kibana': [],
                    'java-11-amazon-corretto-headless': [],
                    'jq': [],
                }
            },
            commands={
                '01_disable-epel': {
                    'command': 'yum-config-manager --disable epel >/dev/null'
                },
                '02_install-ES-plugin-discovery-ec2': {
                    'cwd': '/usr/share/elasticsearch/bin',
                    'command': './elasticsearch-plugin install --batch discovery-ec2',
                    'test': 'test ! -e /usr/share/elasticsearch/plugins/discovery-ec2'
                },
                '03_install-ES-plugin-repository-s3': {
                    'cwd': '/usr/share/elasticsearch/bin',
                    'command': './elasticsearch-plugin install --batch repository-s3',
                    'test': 'test ! -e /usr/share/elasticsearch/plugins/repository-s3'
                },
                '06_install-ES-plugin-analysis-icu': {
                    'cwd': '/usr/share/elasticsearch/bin',
                    'command': './elasticsearch-plugin install --batch analysis-icu',
                    'test': 'test ! -e /usr/share/elasticsearch/plugins/analysis-icu'
                },
                '07_configure_kibana': {
                    'command': 'sed -i \'/^#server.host/ s/localhost/0.0.0.0/;/^#server.host/ s/^#//\' /etc/kibana/kibana.yml'
                }
            },
            services={
                'sysvinit': {
                    'elasticsearch': {
                        'enabled': 'false'
                    },
                    'kibana': {
                        'enabled': 'false'
                    }
                }
            }
        ),
        'SERVICES': cfm.InitConfig(
            files={
                '/etc/elasticsearch/elasticsearch.yml': {
                    'content': Join('', [
                        'cluster.name: ' + cfg.Brand + '-elasticsearch\n',
                        'network.host: [\'_local:ipv4_\', \'_site:ipv4_\']\n',
                        'discovery.ec2.groups: ', Ref('SecurityGroupInstancesRules'), '\n'
                        'path.data: /var/lib/elasticsearch\n',
                        'path.logs: /var/log/elasticsearch\n',
                        'discovery.zen.hosts_provider: ec2\n',
                        'discovery.ec2.endpoint: ', Sub('ec2.${AWS::Region}.amazonaws.com'), '\n'
                    ]),
                    'group': 'elasticsearch'
                },
            },
            commands={
                '10-etc_sysconfig_elasticsearch': {
                    'command': Join('', [
                        'export MY_ES_HEAP_SIZE=$(expr $(grep "MemTotal:" /proc/meminfo | egrep -o "([[:digit:]]+)") / 1000 / 2)m;',
                        'echo -e "# Heap size defaults to 256m min, 1g max\n',
                        '# Set ES_HEAP_SIZE to 50% of available RAM, but no more than 31g\n',
                        'ES_JAVA_OPTS=\\"-Xms${MY_ES_HEAP_SIZE} -Xmx${MY_ES_HEAP_SIZE} -XX:NewRatio=6\\"" > /etc/sysconfig/elasticsearch',
                        ' && chgrp elasticsearch /etc/sysconfig/elasticsearch'
                    ])
                }
            },
            services={
                'sysvinit': {
                    'elasticsearch': {
                        'ensureRunning': 'true',
                        'files': [
                            '/etc/elasticsearch/elasticsearch.yml',
                            '/etc/sysconfig/elasticsearch'
                        ]
                    },
                    'kibana': {
                        'ensureRunning': 'true',
                    },
                }
            }
        )
    })

    return init_args
