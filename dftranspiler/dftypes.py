
class Number:
    """
    Represents a DF Number Value

    Parameters
    ----------

    value : str
        Value of the number (must be string)

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, value, slot=0):
        self.item = {
            "id": "num",
            "data": {
               "name": value
            }
        }
        self.slot = slot


class Text:
    """
    Represents a DF Text Value

    Parameters
    ----------

    value : str
        String that represents the value

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, value, slot=0):
        self.item = {
            "id": "txt",
            "data": {
               "name": value
            }
        }
        self.slot = slot


class Variable:
    """
    Represents a DF Variable

    Parameters
    ----------

    name : str
        Name of the variable (must be string)

    (optional) scope : str
        The scope of the variable
        The scope can be one of: local (LOCAL), saved (SAVE), unsaved (GAME)

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, name, scope="local", slot=0):
        self.item = {
            "id": "var",
            "data": {
               "name": name,
               "scope": scope
            }
        }
        self.slot = slot


class Location:
    """
    Represents a DF Location Value

    Parameters
    ----------

    x : float
    y : float
    z : float
    pitch: float
    yaw: float

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, x=0.0, y=0.0, z=0.0, pitch=0.0, yaw=0.0, slot=0):
        self.item = {
            "id": "loc",
            "data": {
                "loc": {"x": x, "y": y, "z": z, "pitch": pitch, "yaw": yaw},
                "isBlock": False
            }
        }
        self.slot = slot


class Item:
    """
    Represents a DF Item Value

    Parameters
    ----------

    nbt : string
        NBT Data for the item (eg. {id:"minecraft:stone",Count:1b})

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, nbt="{id:\"minecraft:stone\",Count:1b}", slot=0):
        self.item = {
            "id": "item",
            "data": {
                "item": nbt
            }
        }
        self.slot = slot


class GameValue:
    """
    Represents a DF Game Value

    Parameters
    ----------

    gval : string
        The name of the game value (You can find it on the server iself)

    (optional) target : string
        The target selector (Check on the server as well)

    (optional) slot : int
        The slot the value is in

    """
    def __init__(self, gval, target="Default", slot=0):
        self.item = {
            "id": "g_val",
            "data": {
                "type": gval,
                "target": target
            }
        }
        self.slot = slot


####
# SPECIAL TYPES TO REPRESENT CODE BLOCKS AND STUFF
####

class CodeBlock:
    def __init__(self, type_, event, args=[]):
        self.block = type_
        self.id = "block"
        self.args = {"items": args}
        self.action = event


class Bracket:
    def __init__(self, direct="open", type_="norm"):
        self.id = "bracket"
        self.direct = direct
        self.type = type_


class FuncProc:
    def __init__(self, name, type_="func", hidden="False"):
        self.block = type_
        self.id = "block"
        self.args = {"items": [{
            "item": {
              "id": "bl_tag",
              "data": {
                "option": hidden,
                "tag": "Is Hidden",
                "action": "dynamic",
                "block": type_
              }
            },
            "slot": 26
        }]}
        self.data = name