#!/bin/bash -eux
ENV=_IBOX_CODE_Ref('Env')_IBOX_CODE_
ENVABBR=_IBOX_CODE_Ref('EnvShort')_IBOX_CODE_
ENVACCOUNTID=_IBOX_CODE_Ref("AWS::AccountId")_IBOX_CODE_
ENVROLE=_IBOX_CODE_Ref('EnvRole')_IBOX_CODE_
ENVBRAND=_IBOX_CODE_str(cfg.BrandDomain)_IBOX_CODE_
STACKNAME=_IBOX_CODE_Ref('AWS::StackName')_IBOX_CODE_
REGION=_IBOX_CODE_Ref('AWS::Region')_IBOX_CODE_
SIGNAL=_IBOX_CODE_If('DoNotSignal', '', 'yes')_IBOX_CODE_

SIGNAL(){
  case $? in
    0)
     status=SUCCESS
     ;;
    *)
     status=FAILURE
     ;;
  esac
  IMDSv2_token=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  instance_id=$(curl -H "X-aws-ec2-metadata-token: $IMDSv2_token" -s http://169.254.169.254/latest/meta-data/instance-id)
  # avoid exiting with error if stack is in UPDATE_COMPLETE state and cannot be signaled
  aws --region $REGION cloudformation signal-resource --stack-name $STACKNAME --logical-resource-id AutoScalingGroup --unique-id $instance_id --status $status || :
  if [ "$status" = "FAILURE" ];then
    shutdown -h now
  fi

}

if [ -n "$SIGNAL" ];then
  trap SIGNAL EXIT ERR
fi

cat > /etc/profile.d/ibox_env.sh << EOF
#setup ibox environment variables
export Env=${ENV}
export EnvAbbr=${ENVABBR}
export EnvRegion=${REGION}
export EnvAccountId=${ENVACCOUNTID}
export EnvRole=${ENVROLE}
export EnvBrand=${ENVBRAND}
export EnvStackName=${STACKNAME}
EOF
export BASH_ENV=/etc/profile.d/ibox_env.sh
export ENV=$BASH_ENV

SERVICE_ROLE(){
  cat > /etc/ecs/ecs.config << EOF
ECS_CLUSTER=_IBOX_CODE_Ref('Cluster')_IBOX_CODE_
ECS_ENABLE_SPOT_INSTANCE_DRAINING=true
ECS_IMAGE_PULL_BEHAVIOR=once
ECS_WARM_POOLS_CHECK=true
ECS_NUM_IMAGES_DELETE_PER_CYCLE=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsNumImagesDeletePerCycle')_IBOX_CODE_
ECS_ENGINE_TASK_CLEANUP_WAIT_DURATION=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsEngineTaskCleanupWaitDuration')_IBOX_CODE_
ECS_IMAGE_CLEANUP_INTERVAL=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsImageCleanupInterval')_IBOX_CODE_
ECS_IMAGE_MINIMUM_CLEANUP_AGE=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsImageMinimumCleanupAge')_IBOX_CODE_
ECS_ENABLE_UNTRACKED_IMAGE_CLEANUP=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsEnableUntrackedImageCleanup')_IBOX_CODE_
NON_ECS_IMAGE_MINIMUM_CLEANUP_AGE=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgNonEcsImageMinimumCleanupAge')_IBOX_CODE_
ECS_EXCLUDE_UNTRACKED_IMAGE=_IBOX_CODE_get_endvalue('ECSClusterBaseAgentCfgEcsExcludeUntrackedImage')_IBOX_CODE_
EOF
}

SERVICE_ROLE
