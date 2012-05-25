from crow2 import hook
from crow2.events import HookMultiplexer, CommandHook, Hook
from crow2.util import AttrDict
from crow2 import log

config_hooks = hook.createsub("config", default_hook_class=HookMultiplexer)

chooseconfig_hook = config_hooks.createhook("chooseconfig", hook_class=Hook)
loadhook = config_hooks.createhook("loadconfig", childarg="config_type", preparer=chooseconfig_hook)

newconfig_hook = config_hooks.createhook("new", hook_class=Hook)
writehook = config_hooks.createhook("writeconfig", childarg="config_type", preparer=newconfig_hook)

@loadhook("yaml")
def load_yaml(event):
    raise NotImplementedError("fixme")

@loadhook("json")
def load_json(event):
    import json
    load_with(json, event)

def load_with(loader, event):
    try:
        reader = open(event.filename)
    except IOError as e:
        if e.errno == 2:
            log.msg("No config found.")
    else:
        config = loader.load(reader)
        event.config.update(config)

@writehook("yaml")
def write_yaml(event):
    raise NotImplementedError("fixme")

@writehook("json")
def write_json(event):
    import json
    writer = open(event.filename, "w")
    json.dump(event.config, writer, indent=4, sort_keys=True)


@hook.init(tag="config")
def config(event):
    config_type = "json"
    filename = "config." + config_type
    config = AttrDict()

    load_event = loadhook.fire(event, config_type=config_type, filename=filename, config=config)
    config = to_attrdict(load_event.config)

    write_event = writehook.fire(event, config_type=config_type, filename=filename, config=config)
    config = to_attrdict(write_event.config)

    event.main.config = config
    event.config = config

def to_attrdict(obj, recurse=True):
    # todo: this should probably be interface-based since it does type checking
    if isinstance(obj, dict):
        obj = AttrDict(obj)
        if recurse:
            for key in obj:
                res = to_attrdict(obj[key])
                obj[key] = res
    return obj
