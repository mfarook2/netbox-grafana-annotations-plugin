"""
NetBox Grafana Annotations Plugin

Plugin configuration for NetBox Grafana Annotations Plugin.

For a complete list of PluginConfig attributes, see:
https://docs.netbox.dev/en/stable/plugins/development/#pluginconfig-attributes
"""

__author__ = """Mohammad Farook"""
__email__ = "farookconsult@gmail.com"
__version__ = "0.1.0"


from netbox.plugins import PluginConfig


class GrafanaannotationsConfig(PluginConfig):
    name = "netbox_grafana_annotations_plugin"
    verbose_name = "NetBox Grafana Annotations Plugin"
    description = "NetBox plugin for Grafana Annotations."
    author= "Mohammad Farook"
    author_email = "farookconsult@gmail.com"
    version = __version__
    base_url = "netbox_grafana_annotations_plugin"
    min_version = "4.6.0"
    max_version = "4.6.99"


config = GrafanaannotationsConfig
