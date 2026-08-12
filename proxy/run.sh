#!/bin/sh

set -e

# Substitute environment variables in the .conf! Very handy...
envsubst < /etc/nginx/default.conf.tpl > /etc/nginx/conf.d/default.conf
nginx -g 'daemon off;'
