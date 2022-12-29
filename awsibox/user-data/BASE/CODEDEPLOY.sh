CODEDEPLOY(){
  cat >> /etc/codedeploy-agent/conf/codedeployagent.yml << EOF
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
  curl "https://aws-codedeploy-${REGION}.s3.amazonaws.com/latest/install" -o /tmp/codedeployinstall.sh && \
    chmod +x /tmp/codedeployinstall.sh && /tmp/codedeployinstall.sh auto
  service codedeploy-agent disable && service codedeploy-agent start
}
