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

}

trap signal EXIT
