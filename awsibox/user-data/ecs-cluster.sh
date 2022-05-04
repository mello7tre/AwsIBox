#!/bin/bash -eu
STACKNAME=IBOX_CODE_IN_USER_DATARef('AWS::StackName')IBOX_CODE_IN_USER_DATA
REGION=IBOX_CODE_IN_USER_DATARef('AWS::Region')IBOX_CODE_IN_USER_DATA
ACCOUNTID=IBOX_CODE_IN_USER_DATARef('AWS::AccountId')IBOX_CODE_IN_USER_DATA
ENV=IBOX_CODE_IN_USER_DATARef('Env')IBOX_CODE_IN_USER_DATA
ENVSHORT=IBOX_CODE_IN_USER_DATARef('EnvShort')IBOX_CODE_IN_USER_DATA
ENVROLE=IBOX_CODE_IN_USER_DATARef('EnvRole')IBOX_CODE_IN_USER_DATA
BRAND=IBOX_CODE_IN_USER_DATAstr(cfg.BrandDomain)IBOX_CODE_IN_USER_DATA

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
ECS_CLUSTER=IBOX_CODE_IN_USER_DATARef('Cluster')IBOX_CODE_IN_USER_DATA
ECS_ENABLE_SPOT_INSTANCE_DRAINING=true
ECS_IMAGE_PULL_BEHAVIOR=once
ECS_WARM_POOLS_CHECK=true
EOF
