FROM baserow/backend:1.21.2

USER root

COPY ./plugins/upub/ $BASEROW_PLUGIN_DIR/upub/
RUN /baserow/plugins/install_plugin.sh --folder $BASEROW_PLUGIN_DIR/upub

USER $UID:$GID
