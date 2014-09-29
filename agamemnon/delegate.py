import logging

log = logging.getLogger(__name__)

class Delegate(object):
    def __init__(self):
        self.plugins = []

    def load_plugins(self,plugin_dict):
        for key,config in plugin_dict.items():
            try:
                module_name, cls_name = config['classname'].rsplit('.',1)
                module = __import__(module_name, fromlist=[cls_name])
                cls = getattr(module, cls_name)
                plugin = cls(**config['plugin_config'])
                self.__dict__[key]=plugin
                self.plugins.append(key)
            except Exception:
                # TODO: Don't catch all exceptions.
                log.exception("Can't load plugin: %s", key)

    def on_create(self,node):
        for plugin in self.plugins:
            plugin_object = self.__dict__[plugin]
            plugin_object.on_create(node)

    def on_delete(self,node):
        for plugin in self.plugins:
            plugin_object = self.__dict__[plugin]
            plugin_object.on_delete(node)

    def on_modify(self,node):
        for plugin in self.plugins:
            plugin_object = self.__dict__[plugin]
            plugin_object.on_modify(node)

    def __getattr__(self, item):
        if not item in self.__dict__:
            for plugin in self.plugins:
                plugin_object_wrapper = self.__dict__[plugin]
                try:
                    attr = getattr(plugin_object_wrapper,item)
                    return attr
                except AttributeError:
                    pass
            raise AttributeError("No plugin has attribute: {0}".format(item))

