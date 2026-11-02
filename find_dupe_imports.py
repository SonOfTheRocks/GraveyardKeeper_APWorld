import sys, importlib, os
root = os.getcwd()
worlds_dir = os.path.join(root, 'worlds')
custom_rules_path = os.path.join(root, 'worlds', 'graveyard_keeper', 'logic', 'custom_rules.py')
print('custom_rules_path=', custom_rules_path)

def snapshot_imports():
    return {name: getattr(mod, '__file__', None) for name, mod in sys.modules.items() if mod and getattr(mod, '__file__', None) and custom_rules_path in os.path.abspath(getattr(mod, '__file__', ''))}

# ensure clean
for k in list(sys.modules.keys()):
    if 'graveyard_keeper' in k:
        del sys.modules[k]

print('\n--- Import with project root on sys.path ---')
if sys.path[0] != root:
    sys.path.insert(0, root)
else:
    sys.path[0] = root
print('sys.path[0]=', sys.path[0])
try:
    m = importlib.import_module('worlds.graveyard_keeper')
    print('imported worlds.graveyard_keeper ->', getattr(m,'__file__', None), id(m))
except Exception as e:
    print('import worlds.graveyard_keeper failed:', e)
print('snapshot:', snapshot_imports())

# clear again
for k in list(sys.modules.keys()):
    if 'graveyard_keeper' in k:
        del sys.modules[k]

print('\n--- Import with worlds/ on sys.path ---')
if sys.path[0] != worlds_dir:
    sys.path.insert(0, worlds_dir)
else:
    sys.path[0] = worlds_dir
print('sys.path[0]=', sys.path[0])
try:
    m = importlib.import_module('graveyard_keeper')
    print('imported graveyard_keeper ->', getattr(m,'__file__', None), id(m))
except Exception as e:
    print('import graveyard_keeper failed:', e)
print('snapshot:', snapshot_imports())

# final list of all modules with this file
print('\n--- All loaded modules referencing that file ---')
for name, mod in list(sys.modules.items()):
    f = getattr(mod, '__file__', None)
    if f and os.path.abspath(custom_rules_path) == os.path.abspath(f):
        print(name, f, id(mod))
