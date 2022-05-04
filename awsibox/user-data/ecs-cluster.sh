#!/bin/bash -eu
STACKNAME=IBOX_CODE_IN_USER_DATARef('AWS::StackName')IBOX_CODE_IN_USER_DATA
REGION=IBOX_CODE_IN_USER_DATARef('AWS::Region')IBOX_CODE_IN_USER_DATA

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
  aws --region $REGION cloudformation signal-resource --stack-name $STACKNAME --logical-resource-id AutoScalingGroup --unique-id $instance_id --status $status

}

trap signal EXIT

cat >> /etc/ecs/ecs.config << EOF
ECS_CLUSTER=IBOX_CODE_IN_USER_DATARef('Cluster')IBOX_CODE_IN_USER_DATA
ECS_ENABLE_SPOT_INSTANCE_DRAINING=true
ECS_IMAGE_PULL_BEHAVIOR=once
ECS_WARM_POOLS_CHECK=true
EOF
