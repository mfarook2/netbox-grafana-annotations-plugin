"""
Navigation menu items for NetBox Grafana Annotations Plugin.

For more information on navigation menus, see:
https://docs.netbox.dev/en/stable/plugins/development/navigation/
"""

from netbox.plugins import PluginMenuItem

menu_items = (
    PluginMenuItem(
        link="plugins:netbox_grafana_annotations_plugin:annotationlog_list",
        link_text="Annotation Logs",
    ),
)
