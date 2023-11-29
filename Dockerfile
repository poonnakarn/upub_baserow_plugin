FROM baserow/baserow:1.21.2

COPY ./plugins/upub/ /baserow/plugins/upub/
RUN /baserow/plugins/install_plugin.sh --folder /baserow/plugins/upub
