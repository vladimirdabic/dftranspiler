import sys
from dftranspiler import DFTranspiler


if len(sys.argv) < 2:
    print("Usage: dftranspiler <file name>")
    sys.exit(0)

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    code = f.read()

transpiler = DFTranspiler()

try:
    parseresult = transpiler.parse(code)
except Exception as e:
    print(e)
else:
    print(parseresult.give_command())

