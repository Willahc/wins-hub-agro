#!/bin/sh
# Roda DENTRO do container certbot após renovação bem-sucedida.
# O certbot não enxerga o docker do host, então só deixa uma flag;
# o cron do host (reload_nginx_cert.sh) vê a flag e recarrega o nginx.
touch /etc/letsencrypt/.nginx-reload-needed
