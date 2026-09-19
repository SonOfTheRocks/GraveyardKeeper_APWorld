import sys, os, importlib
root = os.getcwd()
print('cwd=', root)
worlds_dir = os.path.join(root, 'worlds')
print('worlds_dir=', worlds_dir)
# Simulate runner that has worlds/ on sys.path (causes top-level graveyard_keeper name)
sys.path.insert(0, worlds_dir)
print('sys.path[0]=', sys.path[0])
try:
    m_top = importlib.import_module('graveyard_keeper')
    print('imported graveyard_keeper ->', getattr(m_top, '__file__', None), id(m_top))
except Exception as e:
    print('import graveyard_keeper failed:', e)
# Now import canonical name
try:
    m_can = importlib.import_module('worlds.graveyard_keeper')
    print('imported worlds.graveyard_keeper ->', getattr(m_can, '__file__', None), id(m_can))
except Exception as e:
    print('import worlds.graveyard_keeper failed:', e)
print('modules with graveyard_keeper in name:')
for k in sorted([k for k in sys.modules if 'graveyard_keeper' in k]):
    mod = sys.modules[k]
    print(k, getattr(mod, '__file__', None), id(mod))
