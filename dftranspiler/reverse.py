import json
from .funcbind import actiondata


class DFReverseTranspiler:

    def __init__(self):
        self.cb_functions = {
            "SendMessage": "Send",
            "ActionBar": "ActionBar",
            "Teleport": "Teleport",
            "RngTeleport": "RandomTeleport",
            "GiveItems": "Give",
            "SetArmor": "SetArmor",
            "SetItems": "SetItems",
            "SetAllowPVP": "SetPVP",
            "ClearInv": "ClearInv",
            "Wait": "Wait",
            "ShowInv": "GUI.Open",
            "CloseInv": "GUI.Close",
            "ExpandInv": "GUI.Expand",
            "SetMenuItem": "GUI.SetItem",
            "RemoveInvRow": "GUI.RemoveRow",
            "SetListValue": "list.set"
        }

        self.indent = 0

    def parse(self, txt):
        
        # TODO: decompress gzip
        self.indent = 0

        template_data = json.loads(txt)
        blocks = template_data["blocks"]

        lines = []

        for block in blocks:
            lines.extend(self.parse_df_value(block))
        
        return '\n'.join(lines)+"\n}"

    def parse_tags(self, data, inpdata={}):
        tagdata = data['data']
        option = tagdata['option']
                
        for btag in actiondata[inpdata['cb']]['tags']:
            if btag['name'] != tagdata['tag']: continue

            if btag['defaultOption'] != option:
                return f"\"{tagdata['tag']}\": \"{option}\""

    def parse_df_value(self, data, inpdata={}):
        # parse item if its an item
        if "item" in data:
            loopidx = inpdata["slot"]
            itemdata = data["item"]
            itemslot = data["slot"]
            itemtype = itemdata["id"]

            slot = f"({itemslot})" if itemslot != loopidx else ""

            if itemtype == "var":
                vname = itemdata["data"]["name"]
                scope = itemdata["data"]["scope"]
                # check for spaces
                if " " in vname: vname = f"<{vname}>"
                # check for type
                scopetype = inpdata.get("scope_type", "reference")
                if scopetype == "reference": scope = "(save)" if scope == "saved" else "(game)" if scope == "unsaved" else ""
                else:
                    if loopidx == 0:
                        scope = "save " if scope == "saved" else "game " if scope == "unsaved" else ""
  
                return f"{scope}{vname}{slot}"

            elif itemtype == "num": return f"{itemdata['data']['name']}{slot}"
            elif itemtype == "txt": return f"\"{itemdata['data']['name']}\"{slot}"
            elif itemtype == "loc":
                coords = itemdata["data"]["loc"]
                return f"{{{coords['x']}, {coords['y']}, {coords['z']}, {coords['pitch']}, {coords['yaw']}}}{slot}"
            
            elif itemtype == "g_val": return f"g<{itemdata['data']['type']}>({itemdata['data']['target']}){slot}"

            elif itemtype == "item": return f"item{itemdata['data']['item']}"

            

        # parse block
        dftype = data["id"]

        if dftype == "block":
            blocktype = data["block"]
            blockargs = data["args"]["items"]
            blockaction = data.get("action", data.get("data", "FailedToFindActionData"))
            blocksub = data.get("subAction", None)

            if blocktype == "event" or blocktype == "process":
                self.indent += 1
                return (f"{blocktype} {blockaction}\n{{",)

            if blockaction in self.cb_functions:
                cbtxtaction = self.cb_functions[data["action"]]
            else:
                if blocksub is not None:
                    cbtxtaction = f"""codeblock {{type:"{blocktype}", action:"{blockaction}", subAction:"{blocksub}"}}"""
                else:
                    cbtxtaction = f"""codeblock {{type:"{blocktype}", action:"{blockaction}"}}"""

            # special syntax
            if blocktype == "set_var":
                txtargs = [self.parse_df_value(arg, {"slot": i, "cb": blockaction, "scope_type": "assign"}) for i, arg in enumerate(blockargs) if arg['item']['id'] != "bl_tag"]
                if blockaction in ["=", "+=", "-="]:
                    if len(txtargs) == 1: return ('\t'*self.indent + f"{txtargs[0]}{'++' if blockaction == '+=' else '--'};",)
                    return ('\t'*self.indent + f"{txtargs[0]} {blockaction} {txtargs[1]};",)

                elif blockaction == "CreateList":
                    return ('\t'*self.indent + f"{txtargs[0]} = [{', '.join(txtargs[1:])}];",)

                elif blockaction in "+-*/":
                    return ('\t'*self.indent + f"{txtargs[0]} = {txtargs[1]} {blockaction} {txtargs[2]};",)

                elif blockaction == "GetListValue":
                    return ('\t'*self.indent + f"{txtargs[0]} = {txtargs[1]}[{txtargs[2]}];",)

            elif blocktype == "if_var":
                if blockaction in ["=", "!=", ">", "<", ">=", "<="]:
                    return ('\t'*self.indent + f"if var({txtargs[0]} {'==' if blockaction == '=' else blockaction} {txtargs[1]})\n",)

                elif blockaction == "VarExists":
                    return ('\t'*self.indent + f"if var({txtargs[0]})\n",)

                elif blockaction == "ListContains":
                    return ('\t'*self.indent + f"if var({txtargs[1]} in {txtargs[0]})\n",)

                elif blockaction == "InRange":
                    return ('\t'*self.indent + f"if var({txtargs[1]} in {txtargs[0]})\n",)

            # parse args
            txtargs = [self.parse_df_value(arg, {"slot": i, "cb": blockaction}) for i, arg in enumerate(blockargs) if arg['item']['id'] != "bl_tag"]
            tags = []
            for arg in blockargs:
                if arg['item']['id'] == "bl_tag":
                    tagrepr = self.parse_tags(arg['item'], {"cb": blockaction})
                    if tagrepr is not None: tags.append(tagrepr)

            tagstr = " {"+', '.join(tags)+"}" if len(tags) != 0 else ""

            

            return ('\t'*self.indent + f"{cbtxtaction} ({', '.join(txtargs)}){tagstr};",)
            #return 
            
        elif dftype == "bracket":
            if data['direct'] == "open":
                val = ('\t'*self.indent+"{",)
                self.indent += 1
                return val    
            elif data['direct'] == "close":
                self.indent -= 1
                return ('\t'*self.indent+"}",)