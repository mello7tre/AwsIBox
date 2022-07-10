#!/bin/bash -eu
STACKNAME=_IBOX_CIUD_Ref('AWS::StackName')_IBOX_CIUD_
REGION=_IBOX_CIUD_Ref('AWS::Region')_IBOX_CIUD_
ACCOUNTID=_IBOX_CIUD_Ref('AWS::AccountId')_IBOX_CIUD_
ENV=_IBOX_CIUD_Ref('Env')_IBOX_CIUD_
ENVSHORT=_IBOX_CIUD_Ref('EnvShort')_IBOX_CIUD_
ENVROLE=_IBOX_CIUD_Ref('EnvRole')_IBOX_CIUD_
BRAND=_IBOX_CIUD_str(cfg.BrandDomain)_IBOX_CIUD_

signal(){
  case $? in
    0)
     status=SUCCESS
     ;;
    *)
     status=FAILURE
     ;;
  esac
  instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
  # avoid exiting with error if stack is in UPDATE_COMPLETE state and cannot be signaled
  aws --region $REGION cloudformation signal-resource --stack-name $STACKNAME --logical-resource-id AutoScalingGroup --unique-id $instance_id --status $status || :

}

trap signal EXIT

cat >> /etc/profile.d/ibox_env.sh << EOF
#setup ibox environment variables
export Env=$ENV
export EnvAbbr=$ENVSHORT
export EnvRegion=$REGION
export EnvAccountId=$ACCOUNTID
export EnvRole=$ENVROLE
export EnvBrand=$BRAND
export EnvStackName=$STACKNAME
EOF

cat >> /etc/ecs/ecs.config << EOF
ECS_CLUSTER=_IBOX_CIUD_Ref('Cluster')_IBOX_CIUD_
ECS_ENABLE_SPOT_INSTANCE_DRAINING=true
ECS_IMAGE_PULL_BEHAVIOR=once
ECS_WARM_POOLS_CHECK=true
ECS_ENGINE_TASK_CLEANUP_WAIT_DURATION=_IBOX_CIUD_get_endvalue('ECSClusterBaseAgentCfgEcsEngineTaskCleanupWaitDuration')_IBOX_CIUD_
ECS_IMAGE_CLEANUP_INTERVAL=_IBOX_CIUD_get_endvalue('ECSClusterBaseAgentCfgEcsImageCleanupInterval')_IBOX_CIUD_
ECS_IMAGE_MINIMUM_CLEANUP_AGE=_IBOX_CIUD_get_endvalue('ECSClusterBaseAgentCfgEcsImageMinimumCleanupAge')_IBOX_CIUD_
EOF
