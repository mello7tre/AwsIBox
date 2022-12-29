CLOUDWATCH(){
  HELPER_INSTALL amazon-cloudwatch-agent

  cat >> /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
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
      }
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
EOF
  service amazon-cloudwatch-agent start
}
