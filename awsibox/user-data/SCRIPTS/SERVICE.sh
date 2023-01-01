SERVICE(){
  if [ -n "$CLOUDWATCH" ];then
    cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
  "metrics": {
    "append_dimensions": {
      "AutoScalingGroupName": "\${aws:AutoScalingGroupName}",
      "InstanceId": "\${!aws:InstanceId}"
    },
    "aggregation_dimensions": [
      ["AutoScalingGroupName"]
    ],
    "metrics_collected": {
      "mem": {
        "measurement": [
          "mem_used_percent"
        ]
      },
      "disk": {
        "resources": [
          "/"
        ],
        "measurement": [
          {
            "name": "disk_used_percent",
            "rename": "root_disk_used_percent"
          }
        ],
        "drop_device": true
      }
    }
  }
}
EOF
    service amazon-cloudwatch-agent start
  fi

  if [ -n "$CODEDEPLOY" ];then
    cat > /etc/codedeploy-agent/conf/codedeployagent.yml << EOF
---
:log_aws_wire: false
:log_dir: '/var/log/aws/codedeploy-agent/'
:pid_dir: '/opt/codedeploy-agent/state/.pid/'
:program_name: codedeploy-agent
:root_dir: '/opt/codedeploy-agent/deployment-root'
:verbose: false
:wait_between_runs: 1
:proxy_uri:
:max_revisions: 2
EOF
    service codedeploy-agent start
  fi
}

