import importlib
import importlib as _importlib
import sys
import builtins
orig_import = builtins.__import__

def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
    res = orig_import(name, globals, locals, fromlist, level)
    try:
        if 'graveyard_keeper' in name or 'custom_rules' in name:
            mod = sys.modules.get(name)
            print('imported ->', name, 'module-file=', getattr(mod,'__file__', None))
        # also check fromlist modules
        if fromlist:
            for sub in fromlist:
                full = f"{name}.{sub}"
                mod = sys.modules.get(full)
                if mod and ('graveyard_keeper' in full or 'custom_rules' in full):
                    print('fromlist imported ->', full, 'module-file=', getattr(mod,'__file__', None))
    except Exception as e:
        print('hook error', e)
    return res

builtins.__import__ = hooked_import

import pytest
print('starting pytest')
pytest.main(['-q','worlds/graveyard_keeper','--collect-only'])
