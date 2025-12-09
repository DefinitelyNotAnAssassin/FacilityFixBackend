import sys, os, importlib.util
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print('repo_root', repo_root)
if repo_root not in sys.path:
    sys.path.append(repo_root)

print('sys.path includes repo_root:', repo_root in sys.path)
print('app spec:', importlib.util.find_spec('app'))
print('app.type_task_id_ spec:', importlib.util.find_spec('app.type_task_id_'))
print('app.services spec:', importlib.util.find_spec('app.services'))
print('\nAvailable app submodules:')
import pkgutil
spec = importlib.util.find_spec('app')
if spec is not None and spec.submodule_search_locations:
    for finder, name, ispkg in pkgutil.iter_modules(spec.submodule_search_locations):
        print(' -', name, ' (pkg: ', ispkg, ')')
else:
    print('No app submodules found')