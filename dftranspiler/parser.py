import json
import gzip
import base64
import os
import os.path
import re
from lark import Lark, Transformer, v_args, Token, UnexpectedToken
from pathlib import Path
from .dftypes import *
from .funcbind import exec_bound, jsonargs, actiondata, funcbind, tags


# Parser functions
# parserfuncs = {}

# Function Data (args)
funcdata = {}


@v_args(inline=True)
class Parser(Transformer):

    constants = {}
    var_bind_types = {
        "game": "unsaved",
        "global": "unsaved",
        "save": "saved",
        "saved": "saved",
        "local": "local"
    }

    statements = lambda self, *nodes: list(nodes)
    suite      = lambda self, tree: tree
    kv_pair    = lambda self, k, v: (k.value[1:-1], v.value[1:-1])
    kv_list    = lambda self, *elements: elements
    dict_val   = lambda self, vals: dict(vals)
    number     = lambda self, tok: Number(tok.value)
    truev      = lambda self, tok: Number("1")
    falsev     = lambda self, tok: Number("0")
    string     = lambda self, tok: Text(tok.value[1:-1].replace("\\\"", "\"").replace("\\'", "'"))
    #item_val   = lambda self, nbt: Item(nbt.value.replace("\n", "").replace("\r", "").replace("\\n", "\n"))
    item_val   = lambda self, nbt: Item(nbt)
    loc_val    = lambda self, x, y, z, pitch=None, yaw=None: Location(float(x.value), float(y.value), float(z.value), 0.0 if pitch is None else float(pitch.value), 0.0 if yaw is None else float(yaw.value))
    game_val   = lambda self, gval, selector=None: GameValue(gval.value[1:-1], target="Default" if selector is None else selector.value[1:-1])
    exprlist   = lambda self, *tree: list(tree)
    namelist   = lambda self, *tree: list(name.value for name in tree)
    ifvarexpr  = lambda self, v1, op, v2: (op.value, v1, v2)
    ifvarexist = lambda self, v: ('VarExists', v)
    ifinrange  = lambda self, val, ink, min_, commac=None, max_=None: ('ListContains', min_, val) if commac is None else ('InRange', val, min_, max_)
    #ifinlist   = lambda self, vals, lst_val: ('ListContains', lst_val, *vals)
    iftype     = lambda self, typekw, val: ('VarIsType', val)

    # NBT sturcture
    nbt_data   = lambda self, vals: make_nbt(vals)
    nbt_dict   = lambda self, vals: vals
    nbt_kv_list= lambda self, *elements: elements
    nbt_kv     = lambda self, k, v: (k.value, v)
    nbt_value  = lambda self, val: val.value if isinstance(val, Token) else val
    nbt_list   = lambda self, elements: elements
    nbt_val_list = lambda self, *elements: elements
    nbt_byte_num = lambda self, number: number.value + "b"

    def atom_slot(self, value, slot):
        value.slot = int(slot.value)
        return value

    event_def  = lambda self, name, body: ('def', 'event', name.value, body, {})
    #func_def   = lambda self, name, body: ('def', 'func', name.value, body, {"hidden": "False"})
    proc_def   = lambda self, name, body: ('def', 'process', name.value, body, {"hidden": "False"})
    select_stmt = lambda self, name, args=[]: ('cb', CodeBlock("select_obj", name.value, args=jsonargs(args)))

    def func_def(self, name, args, body):
        funcdata[name] = args
        return ('def', 'func', name.value, body, {"hidden": "False"})

    end        = lambda self: ('cb', CodeBlock("control", "End"))
    return_stmt = lambda self: ('cb', CodeBlock("control", "Return"))
    continue_stmt = lambda self: ('cb', CodeBlock("control", "Skip"))
    break_stmt        = lambda self: ('cb', CodeBlock("control", "StopRepeat"))

    
    # RAW CODEBLOCK DEFINITION
    def code_block_def(self, nbtdata, args, tagss={}):
        nbt = make_nbt(nbtdata, txt_repr=False)

        action = nbt.get("action", "SendMessage")
        block = CodeBlock(nbt.get("type", "player_action"), action, args=jsonargs(args) + tags(action))
        apply_tags(block, tagss)

        if "target" in nbt: block.target = nbt["target"]
        if "inverted" in nbt: block.inverted = nbt["inverted"]
        if "subAction" in nbt: block.subAction = nbt["subAction"]

        return('cb', block)


    #parserfunc = lambda self, name, args: (ret := parserfuncs[name.value](*args) if ret is not None else Number()) if name.value in parserfuncs else Number("0")
    # def parserfunc(self, name, args):
    #     if name.value in parserfuncs:
    #         ret = parserfuncs[name.value](*args)
    #         return Number('0') if ret is None else ret
    #     print(f"Unknown function '{name.value}'")
    #     return Number('0')


    def func_call(self, name, selector, args, tagss={}): 
        block = exec_bound(name.value, args, target=selector, return_vars=False)
        apply_tags(block, tagss)
        return('cb', block)

    def var(self, name):

        if name.value in self.constants:
            return self.constants[name.value]

        if name.value[0] == "<" and name.value[-1] == ">": name.value = name.value[1:-1]
        if name.value[0] == "$": return Variable(name.value[1:], scope='unsaved')
        if name.value[0] == "!": return Variable(name.value[1:], scope='saved')

        return Variable(name.value)
    
    def select_stmt_sub(self, name, subaction, args=[]):
        block = CodeBlock("select_obj", name.value, args=jsonargs(args))
        block.subAction = subaction.value
        return ('cb', block)

    def df_func_call(self, name, args):
        # append create list code block for function parameters
        argblock = None
        # if len(args) != 0:
        #     args.insert(0, Variable('args'))
        #     argblock = exec_bound("list.new", args, return_vars=False)

        block = CodeBlock("call_func", None)
        del block.action
        block.data = name.value

        if argblock is None:
            return ('func_cb', block, args)

        return ('unpack', ('cb', argblock), ('func_cb', block, args))

    def df_proc_call(self, name, tagss={}):
        # append create list code block for function parameters
        block = CodeBlock("start_process", None)
        del block.action
        block.data = name.value
        block.args["items"] = actiondata["ProcessTags"]
        apply_tags(block, tagss)

        return ('cb', block)

    def func_call_assign(self, varname, funcname, args):
        codeblock_name = funcbind[funcname]
        varjson = vars(self.var(varname))

        codeblock = CodeBlock("set_var", codeblock_name, args=[varjson]+jsonargs(args, offset=1)+tags(codeblock_name, type_="set_var"))
        return ('cb', codeblock)

    def index_var(self, varname, idx_var, idx):
        varjson = vars(self.var(varname))
        idx.slot = 2

        idx_var = self.var(idx_var)
        idx_var.slot = 1
        idxvarjson = vars(idx_var)

        codeblock = CodeBlock("set_var", "GetListValue", args=[varjson, idxvarjson, vars(idx)])
        return ('cb', codeblock)

    def setvar(self, name, value):
        varref = vars(self.var(name))
        value.slot = 1
        return ('cb', CodeBlock("set_var", "=", args=[varref, vars(value)]))

    def setconst(self, name, value):
        self.constants[name.value] = value

    def setlist(self, name, args):
        varjson = vars(self.var(name))
        codeblock = CodeBlock("set_var", "CreateList", args=[varjson]+jsonargs(args, offset=1))
        return ('cb', codeblock)

    # math operations

    # This can be shrinked down to a lambda using jsonargs()
    def math_operation(self, name, value, value2, op):
        varref = vars(self.var(name))
        value.slot = 1
        value2.slot = 2
        return ('cb', CodeBlock("set_var", op, args=[varref, vars(value), vars(value2)]))

    add = lambda self, name, value, value2: self.math_operation(name, value, value2, "+")
    sub = lambda self, name, value, value2: self.math_operation(name, value, value2, "-")
    mul = lambda self, name, value, value2: self.math_operation(name, value, value2, "*")
    div = lambda self, name, value, value2: self.math_operation(name, value, value2, "/")
    inc = lambda self, name, value=None: ('cb', CodeBlock("set_var", "+=", args=jsonargs([self.var(name), value])))
    dec = lambda self, name, value=None: ('cb', CodeBlock("set_var", "-=", args=jsonargs([self.var(name), value])))


    def if_var(self, expr, tagss, body=None):
        if body is None:
            body = tagss
            tagss = {}
        op = expr[0]
        args = expr[1:]
        op = "=" if op == "==" else op
        cb = CodeBlock("if_var", op, args=jsonargs(args)+tags(op, type_="if_var"))
        apply_tags(cb, tagss)
        return ('unpack', ('cb', cb), ('cb', Bracket()), ('unpack', *body), ('cb', Bracket('close')))

    def if_player(self, cond, args, tagss, body=None):
        if body is None:
            body = tagss
            tagss = {}
        cb = CodeBlock("if_player", cond.value, args=jsonargs(args)+tags(cond.value, type_="if_player"))
        apply_tags(cb, tagss)
        return ('unpack', ('cb', cb), ('cb', Bracket()), ('unpack', *body), ('cb', Bracket('close')))

    def else_stmt(self, body):
        cb = CodeBlock("else", "")
        del cb.action
        del cb.args
        return ('unpack', ('cb', cb), ('cb', Bracket()), ('unpack', *body), ('cb', Bracket('close')))

    def if_game(self, cond, args, tagss, body=None):
        if body is None:
            body = tagss
            tagss = {}
        cb = CodeBlock("if_game", cond.value, args=jsonargs(args)+tags(cond.value, type_="if_game"))
        apply_tags(cb, tagss)
        return ('unpack', ('cb', cb), ('cb', Bracket()), ('unpack', *body), ('cb', Bracket('close')))

    def negateif(self, blocks):
        blocks[1][1].inverted = "NOT"
        return blocks

    def negatewhile(self, blocks):
        cb = blocks[1][1]
        cb.inverted = "NOT"
        if cb.block == "if_var":
            bo = blocks[2][1]
            bc = blocks[4][1]
            cb.block = "repeat"
            cb.subAction = cb.action
            cb.action = "While"
            bo.type = "repeat"
            bc.type = "repeat"

        return blocks

    def while_cond(self, condname, args, tagss, body=None):
        if body is None:
            body = tagss
            tagss = {}

        cb = CodeBlock("repeat", "While", args=jsonargs(args)+tags(condname.value, type_="repeat"))
        cb.subAction = condname.value
        apply_tags(cb, tagss)
        return ('unpack', ('cb', cb), ('cb', Bracket('open', 'repeat')), ('unpack', *body), ('cb', Bracket('close', 'repeat')))

    def while_if_var(self, blocks):
        cb = blocks[1][1]
        bo = blocks[2][1]
        bc = blocks[4][1]
        cb.block = "repeat"
        cb.subAction = cb.action
        cb.action = "While"
        bo.type = "repeat"
        bc.type = "repeat"
        return blocks

    def forever_loop(self, body):
        return ('unpack', ('cb', CodeBlock("repeat", "Forever")), ('cb', Bracket('open', 'repeat')), ('unpack', *body), ('cb', Bracket('close', 'repeat')))

    def hidden_def(self, cb):
        cb[4]["hidden"] = "True"
        return cb

    def scoped_def(self, cb):
        cb[3].insert(0, ('cb', CodeBlock("set_var", "+=", args=jsonargs([Variable("dft.scope")]))))
        ######### Scope clearing disabled until purge local vars is fixed on DF
        # cb[3].append(0, ('cb', CodeBlock("set_var", "PurgeVars", args=jsonargs([Text("dfts:%var(dft.scope)")]) + tags("PurgeVars"))))
        cb[3].append(('cb', CodeBlock("set_var", "-=", args=jsonargs([Variable("dft.scope")]))))
        return cb

    def var_with_type(self, type_, cb=None):
        if cb is None: return type_
        
        if type_.value == "scoped":
            cbname = cb[1].args['items'][0]['item']['data']['name']
            cb[1].args['items'][0]['item']['data']['name'] = "dfts:%var(dft.scope) " + cbname
        else:
            cb[1].args["items"][0]["item"]["data"]["scope"] = self.var_bind_types[type_.value]

        return cb

    def expr_var_type(self, type_, var_obj=None):
        if var_obj is None: return type_
        
        if type_.value == "(scoped)":
            varname = var_obj.item['data']['name']
            var_obj.item['data']['name'] = "dfts:%var(dft.scope) " + varname
        else:
            var_obj.item["data"]["scope"] = self.var_bind_types[type_.value[1:-1]]
            
        return var_obj

#pylint: disable=unbalanced-tuple-unpacking

class TranspilerError(SyntaxError):
    def __str__(self):
        label, context, line, column = self.args
        return '%s at/near line %s, column %s.\n\n%s' % (label, line, column, context)


class DFTranspiler:
    def __init__(self):
        self.lark = Lark(open(Path(__file__).parent/'grammar.lark'), parser='lalr', transformer=Parser(), maybe_placeholders=True, start="statements")

    def parse(self, txt):
        try:
            return DFTranspileResult(self.lark.parse(self.preprocess(txt, included_=[])))
        except UnexpectedToken as u:
            err_msg = u.match_examples(self.lark.parse, {
                "Expected Semi Colon": [
                    "Send (\"Hello\")",
                    "Send (2)"
                    "a = 2",
                    "myvar = []",
                    "game xd = \"hello\"",
                    "item{id:\"test\"}",
                    "const num = 20"
                ],
                "Expected Value": [
                    "myvar = ",
                    "game var = ",
                    "save example = "
                ]
            })

            if err_msg is None: err_msg = "Unexpected Input"
            raise TranspilerError(err_msg, u.get_context(txt), u.line, u.column)

    def preprocess(self, txt, included_=[], binds_=True):

        # process includes
        included = included_
        for line in txt.split("\n"):
            if len(line) == 0: continue
            spaced = line.split()

            if len(spaced) < 2: continue

            if spaced[0] != "#include": continue

            filename = spaced[1].replace(".", "/") + ".df"
            filepath = spaced[1].split(".")
            if filename in included:
                #print(f"{filename} already included")
                txt = txt.replace(line, "")
                continue

            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    txt = txt.replace(line, self.preprocess(f.read(), included_=included, binds_=False))
                    included.append(filename)
                    
            elif os.path.exists(Path(__file__).parent/f'df_files/{filename}'):
                with open(Path(__file__).parent/f'df_files/{filename}', 'r') as f:
                    txt = txt.replace(line, self.preprocess(f.read(), included_=included, binds_=False))
                    included.append(filename)

            elif filepath[-1] == "*":
                final = ""
                final_path = '/'.join(filepath[:-1])
                if not os.path.exists(final_path):
                    final_path = Path(__file__).parent/f'df_files/'/'/'.join(filepath[:-1])
                    if not os.path.exists(final_path): continue

                for filen in os.listdir(final_path):
                    if not filen.endswith(".df"):
                        continue
                    checkp = '/'.join(filepath[:-1] + [filen])
                    if checkp in included:
                        txt = txt.replace(line, "")
                        #print(f"{checkp} already included")
                        continue
                    included.append(checkp)
                    with open(os.path.join(final_path, filen), 'r') as f:
                        final += self.preprocess(f.read(), included_=included, binds_=False)+"\n"
                        
                txt = txt.replace(line, final)

        if not binds_: return txt

        # process definitions
        binds = {}
        for line in txt.split("\n"):
            if len(line) == 0: continue
            spaced = line.split()

            if len(spaced) < 3: continue

            if spaced[0] != "#define": continue

            # TODO: Check if mulitline def

            symbol = spaced[1]
            value = line[len(spaced[0])+len(symbol)+2:]

            args = re.findall(r'\(.*\)', symbol)
            if len(args) == 1:
                binds[symbol[:-len(args[0])]] = {"symbol": symbol, "type": "replace_args", "value": value, "args": args[0][1:-1].split(',')}
                continue

            binds[symbol] = {"symbol": symbol, "type": "replace", "value": value}

        for symbol, data in binds.items():
            txt = txt.replace(f"#define {data['symbol']} {data['value']}", "")

            if data["type"] == "replace":
                txt = re.sub(f'\\b{symbol}\\b', data['value'], txt)
            
            elif data["type"] == "replace_args":
                paren = r'[ubf]?r?(\((?!\(\)).*?(?<!\\)(\\\\)*?\))'
                pattern = f"({symbol}){paren}"
                finds = re.findall(pattern, txt)

                for find in finds:
                    toreplace = f"{find[0]}{find[1]}"
                    args = find[1][1:-1].split(",")
                    val = data["value"]

                    for argval, argname in zip(args, data["args"]):
                        val = val.replace(f"#{argname}", argval)

                    txt = txt.replace(toreplace, val)

        return txt


class DFTranspileResult:
    def __init__(self, tree):
        self.current = None
        self.lines = {}
        self._parse_tree(tree)

    def _parse_tree(self, tree):
        for node in tree:
            if node is None: continue
            if node[0] == "def": #('def', 'process', name.value, body, {"hidden": "False", "type_": "process"})
                if f"{node[1]}:{node[2]}" not in self.lines:
                    self.lines[f"{node[1]}:{node[2]}"] = [vars(CodeBlock(node[1], node[2], **node[4])) if node[1] == "event" else vars(FuncProc(node[2], type_=node[1], **node[4]))]
                
                self.current = self.lines[f"{node[1]}:{node[2]}"]
                self._parse_tree(node[3])

            elif node[0] == "cb": self.current.append(vars(node[1]))
            elif node[0] == "func_cb":
                if node[1].block == "call_func":
                    funcname = node[1].data
                    args = funcdata[funcname]

                    for argname, value in zip(args, node[2]):
                        value.slot = 1
                        self.current.append(vars(CodeBlock("set_var", "=", args=jsonargs([Variable(f"dfts:%math(%var(dft.scope)+1) {argname}"), value]))))

                    self.current.append(vars(node[1]))
                    
            elif node[0] == "unpack": self._parse_tree(node[1:])


    def compressed(self, code_line):
        if code_line not in self.lines:
            raise NameError(f"Unknown code line name '{code_line}'")

        compressed = gzip.compress(self.json(code_line).encode('utf-8'))
        return base64.b64encode(compressed).decode("utf-8")

    def json(self, code_line):
        if code_line not in self.lines:
            raise NameError(f"Unknown code line name '{code_line}'")

        return json.dumps({"blocks": self.lines[code_line]})

    def give_command_item(self, code_line):
        return f"""/give @p minecraft:ender_chest{{PublicBukkitValues:{{"hypercube:codetemplatedata":'{{"author":"DFTranspiler","name":"DFTranspiler Template","version":1,"code":"{self.compressed(code_line)}"}}'}},display:{{Name:'{{"text":"{code_line} Template"}}'}}}}"""

    def _nbt(self, code_line, curslot):
        return f"""{{id: "minecraft:ender_chest", Slot: {curslot}b, Count:1b, tag:{{display:{{Name:'{{"text":"{code_line} Template"}}'}}, PublicBukkitValues:{{"hypercube:codetemplatedata":'{{"author":"DFTranspiler","name":"DFTranspiler Template","version":1,"code":"{self.compressed(code_line)}"}}'}}}}}}"""

    def give_command(self):
        items = []
        for slot, code_line in enumerate(self.lines):
            items.append(self._nbt(code_line, slot))

        return f"""/give @p minecraft:shulker_box{{BlockEntityTag:{{Items:[{','.join(items)}]}}, display:{{Name:'[{{"text": "DFTranspiler Program", "color": "light_purple", "italic": "false"}}]'}}}}"""

def apply_tags(cb, tags):
    for tag, value in tags.items():
        for arg in cb.args["items"]:
            if arg["item"]["id"] == "bl_tag" and arg["item"]["data"]["tag"] == tag:
                arg["item"]["data"]["option"] = value


def make_nbt(tags, txt_repr=True):
    result = {}

    for tag in tags:
        value = tag[1]

        if isinstance(value, tuple):
            result[tag[0]] = make_nbt_list(value, txt_repr=txt_repr)
            continue

        if not txt_repr and value[0] in "\"'":
            value = value[1:-1]

        result[tag[0]] = value

    if not txt_repr: return result
    kvlist = []

    for k, v in result.items():
        kvlist.append(f"{k}:{v}")

    return f"{{{','.join(kvlist)}}}"


def make_nbt_list(vals, txt_repr=True):
    result = []

    for val in vals:

        if isinstance(val, tuple):
            result.append(make_nbt_list(val, txt_repr=txt_repr))
            continue

        result.append(val)

    if not txt_repr: return result
    return f"[{','.join(result)}]"


# Decorator function to bind parser functions
# def parserfunction(*args, **kwargs):
#     def inner(func):
#         fname = kwargs.get('name', func.__name__)
#         parserfuncs[fname] = func
#     if len(args) == 1 and callable(args[0]):
#         return inner(args[0])
#     else:
#         return inner