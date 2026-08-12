FROM nginxinc/nginx-unprivileged:1-alpine
LABEL maintainer="Alex Cave"

COPY ./default.conf.tpl /etc/nginx/default.conf.tpl
COPY ./uwsgi_params /etc/nginx/uwsgi_params
COPY ./run.sh /run.sh

# Environment variables passed into programs.
ENV LISTEN_PORT=80
ENV APP_HOST=app
ENV APP_PORT=8000

USER root

RUN mkdir -p /vol/static && \
    chmod -R 755 /vol/static && \
    # Pre-create the default.conf file and set the owner to nginx.
    touch /etc/nginx/conf.d/default.conf && \
    chown -R nginx:nginx /etc/nginx/conf.d/default.conf && \
    chmod +x /run.sh

VOLUME /vol/static

USER nginx

CMD ["./run.sh"]
