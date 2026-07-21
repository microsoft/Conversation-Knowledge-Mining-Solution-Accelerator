#!/bin/bash

git fetch
git pull

# provide execute permission to quotacheck script
sudo chmod +x ./infra/scripts/pre-provision/checkquota_kmv1.sh
sudo chmod +x ./infra/scripts/pre-provision/quota_check_params.sh
