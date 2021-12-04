#!/bin/bash
[[ $DEBUG ]] && set -x 

RED='\033[0;31m'
GREEN='\033[32;1m'
NC='\033[0m' # No Color

function local_k3s() {
local K3S_DATA_DIR=${K3S_DATA_DIR:-/app/k3s}
local K3S_CONFIG=${K3S_CONFIG:-config.yaml}
local KUBE_CONFIG=${KUBE_CONFIG:-/app/k3s/k3s.yaml}
echo -e "${GREEN}Start initializing Rainbond local k3s cluster,it will be ready in a moment${NC}"
mv /etc/supervisor/conf.d/dind.conf.template /etc/supervisor/conf.d/dind.conf
if [ ! -f ${K3S_DATA_DIR}/${K3S_CONFIG} ];then
    echo -e "${GREEN}Rainbond local k3s cluster config: ${K3S_DATA_DIR}/${K3S_CONFIG}${NC}"
    cp /app/ui/k3s-config.yaml ${K3S_DATA_DIR}/${K3S_CONFIG}
fi
# make kubectl available
echo -e "alias kubectl='kubectl --kubeconfig ${KUBE_CONFIG}'" > ~/.bashrc
}


if [ "${ENABLE_LOCAL_K3s}" == 'true' ];then
    local_k3s # Enable Dind and K3s 
fi

exec $@