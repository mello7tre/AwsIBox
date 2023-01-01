ELBCLASSIC(){
  TOCHECK=_IBOX_CODE_getattr(cfg, 'EC2InstanceUserDataELBClassicCheckLoadBalancerName', '')_IBOX_CODE_
  [ -z "$TOCHECK" ] && return
  state=""
  until [ "$state" = "InService" ]; do
    state=$(aws --region $REGION elb describe-instance-health --load-balancer-name $TOCHECK \
      --instances $(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query InstanceStates[0].State --output text)
    sleep 10
  done
}

ELBV2(){
  TOCHECK=_IBOX_CODE_getattr(cfg, 'EC2InstanceUserDataELBV2CheckTargetGroupArn', '')_IBOX_CODE_
  [ -z "$TOCHECK" ] && return
  state=""
  until [ "$state" = "healthy" ]; do
    state=$(aws --region $REGION elbv2 describe-target-health --target-group-arn $TOCHECK \
      --targets Id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
      --query TargetHealthDescriptions[0].TargetHealth.State --output text)
    sleep 10
  done
}
