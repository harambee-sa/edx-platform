#!/usr/bin/env bash

IP="$(curl -s icanhazip.com)"

echo "Received IP = $IP, deplying to $1"

if [[ "$1" == "development" ]]; then
	echo "Adding IP to EC2"
	aws ec2 authorize-security-group-ingress --group-id $STAGING_SEC_GROUP --protocol tcp --port 22 --cidr "$IP/32"
	sleep 2
	echo "Running play to update Microsites and Assets"
  
  ssh ubuntu@builder.proversity.io "sudo apt-get -y install  git"
  ssh ubuntu@builder.proversity.io "sudo rm -r /edx/app/edxapp/circleci_builds && sudo mkdir -p /edx/app/edxapp && cd /edx/app/edxapp && sudo git clone https://github.com/proversity-org/circleci_builds.git"
  ssh ubuntu@builder.proversity.io "cd /edx/app/edxapp/circleci_builds && sudo /bin/bash run_build.sh development"

	ERROR=$?
	sleep 2
	echo "Removing IP from EC2"
	aws ec2 revoke-security-group-ingress --group-id $STAGING_SEC_GROUP --protocol tcp --port 22 --cidr "$IP/32"
fi


if [[ "$ERROR" -eq 0 ]]; then
  echo "Updated!"
	exit 0
else
  echo "Update failed!"
	exit 1
fi