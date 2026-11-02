import sys,importlib,os
print('cwd=', os.getcwd())
print('sys.path[0]=', sys.path[0])
m1 = importlib.import_module('worlds.graveyard_keeper')
print('imported worlds.graveyard_keeper ->', getattr(m1, '__file__', None), id(m1))
try:
    m2 = importlib.import_module('graveyard_keeper')
    print('imported graveyard_keeper ->', getattr(m2, '__file__', None), id(m2))
except Exception as e:
    print('import graveyard_keeper failed:', e)
mods = [k for k in sys.modules.keys() if 'graveyard_keeper' in k]
print('modules:', mods)
for name in mods:
    mod = sys.modules[name]
    print(name, getattr(mod, '__file__', None), id(mod))
