FROM baserow/web-frontend:1.21.2

USER root

COPY ./plugins/upub/ /baserow/plugins/upub/
RUN /baserow/plugins/install_plugin.sh --folder /baserow/plugins/upub

USER $UID:$GID
