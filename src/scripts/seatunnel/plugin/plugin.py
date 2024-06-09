class SeaTunnelPlugin(object):

    class PluginType:
        IN = 'in'
        OUT = 'out'

    def __init__(self, plugin_type: str, type: str, *args, **kwargs):
        self.plugin_type = plugin_type
        self.type = type
        self._args = args
        self._kwargs = kwargs

    @property
    def config(self) -> str:
        raise NotImplementedError()
    