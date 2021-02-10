from .dftypes import CodeBlock
import requests
from pathlib import Path
from json import loads

# Action data and action tags
#actiondata = requests.get("https://raw.githubusercontent.com/EnjoyYourBan/enjoyyourban.github.io/master/actions.json").json()
actiondataf = open(Path(__file__).parent/'actiondata.json', 'r')
actiondata = loads(actiondataf.read())
actiondataf.close()

# Dictionary for bound functions
funcbind = {}

# Dict for selector types
selectors = {
    "ALL_PLAYERS": "AllPlayers",
    "ALL": "AllPlayers",
    "DEFAULT": "Default",
    "VICTIM": "Victim",
    "KILLER": "Killer",
    "DAMAGER": "Damager",
    "SELECTION": "Selection",
    "ENTITY": "Entity"
}


# Decorator function to bind functions
def bind(*args, **kwargs):
    def inner(func):
        fname = kwargs.get('func', func.__name__)
        funcbind[fname] = func
    if len(args) == 1 and callable(args[0]):
        return inner(args[0])
    else:
        return inner


# Function to put in correct tags for code blocks
def tags(action, type_="player_action"):
    if action not in actiondata: return []
    tags = []
    bdata = actiondata[action]

    for i, tag in enumerate(bdata["tags"]):
        tags.append({
            "item": {
                "id": "bl_tag",
                "data": {
                    "tag": tag["name"],
                    "option": tag["defaultOption"],
                    "action": action,
                    "block": type_
                }
            },
            "slot": 26-i
        })

    return tags


# This function returns the corresponding code block with the bound function
def exec_bound(funcname, args, target=None, return_vars=True):
    if funcname.lower() not in funcbind:
        raise KeyError(f"Unknown function: '{funcname}'")
    block = funcbind[funcname.lower()](jsonargs(args))
    if target is not None: setattr(block, "target", selectors[target])

    if not return_vars: return block
    return vars(block)


# This function turns a list of DF types into their JSON (dict) representation
def jsonargs(args, offset=0):
    jargs = []
    for i, arg in enumerate(args):
        if arg is None: continue
        if arg.slot == 0: arg.slot = i+offset
        jargs.append(vars(arg))
    return jargs


#######################
# ALL BOUND FUNCTIONS #
#######################

# Basic Player Actions
@bind
def send(args):
    return CodeBlock("player_action", "SendMessage", args=args + tags("SendMessage"))

@bind
def actionbar(args):
    return CodeBlock("player_action", "ActionBar", args=args + tags("ActionBar"))

@bind
def teleport(args):
    return CodeBlock("player_action", "Teleport", args=args + tags("Teleport"))

@bind
def randomteleport(args):
    return CodeBlock("player_action", "RngTeleport", args=args + tags("RngTeleport"))

@bind
def give(args):
    return CodeBlock("player_action", "GiveItems", args=args)

@bind
def setarmor(args):
    return CodeBlock("player_action", "SetArmor", args=args)

@bind
def setitems(args):
    return CodeBlock("player_action", "SetItems", args=args)

@bind
def setpvp(args):
    return CodeBlock("player_action", "SetAllowPVP", args=args + tags("SetAllowPVP"))

@bind
def clearinv(args):
    return CodeBlock("player_action", "ClearInv", args=args + tags("ClearInv"))

funcbind["clearinventory"] = funcbind["clearinv"]

# PLAYER GUI
@bind(func='gui.show')
def showgui(args):
    return CodeBlock("player_action", "ShowInv", args=args)

funcbind["gui.open"] = funcbind["gui.show"]

@bind(func='gui.close')
def closegui(args):
    return CodeBlock("player_action", "CloseInv", args=args)

@bind(func='gui.expand')
def expandgui(args):
    return CodeBlock("player_action", "ExpandInv", args=args)

@bind(func='gui.setitem')
def setitemgui(args):
    return CodeBlock("player_action", "SetMenuItem", args=args)

@bind(func='gui.removerow')
def removeguirow(args):
    return CodeBlock("player_action", "RemoveInvRow", args=args + tags("RemoveInvRow"))

# Control Actions
@bind
def wait(args):
    return CodeBlock("control", "Wait", args=args + tags("Wait", "control"))

# Variable actions
@bind(func='list.set')
def setlist(args):
    return CodeBlock("set_var", "SetListValue", args=args)

@bind(func='list.new')
def newlist(args):
    return CodeBlock("set_var", "CreateList", args=args)

funcbind["list.get"] = "GetListValue"
funcbind["list"] = "CreateList"