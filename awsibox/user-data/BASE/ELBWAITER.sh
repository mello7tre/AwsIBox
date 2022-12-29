ELBCLASSICINT(){
  LOADBALANCERCLASSIC=_IBOX_CODE_Ref("LoadBalancerClassicInternal")_IBOX_CODE_
  state=""
  until [ "$state" = "InService" ]; do
    state=$(aws --region $REGION elb describe-instance-health --load-balancer-name $LOADBALANCERCLASSIC \
      --instances $(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query InstanceStates[0].State)
    sleep 10
  done
}

ELBCLASSICIEXT(){
  LOADBALANCERCLASSIC=_IBOX_CODE_Ref("LoadBalancerClassicExternal")_IBOX_CODE_
  state=""
  until [ "$state" = "InService" ]; do
    state=$(aws --region $REGION elb describe-instance-health --load-balancer-name $LOADBALANCERCLASSIC \
      --instances $(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query InstanceStates[0].State)
    sleep 10
  done
}

ELBAPPINT(){
  TARGETGROUP=_IBOX_CODE_Ref("TargetGroupInternal")_IBOX_CODE_
  state=""
  until [ "$state" = "healthy" ]; do
    state=$(aws --region $REGION elbv2 describe-target-health --target-group-arn $TARGETGROUP \
      --targets Id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query TargetHealthDescriptions[0].TargetHealth.State)
    sleep 10
  done
}

ELBAPPEXT(){
  TARGETGROUP=_IBOX_CODE_Ref("TargetGroupExternal")_IBOX_CODE_
  state=""
  until [ "$state" = "healthy" ]; do
    state=$(aws --region $REGION elbv2 describe-target-health --target-group-arn $TARGETGROUP \
      --targets Id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query TargetHealthDescriptions[0].TargetHealth.State)
    sleep 10
  done
}
