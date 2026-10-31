import ctypes
from pathlib import Path
import runpy
import sys
import traceback
import pytest

original_main = pytest.main

def observed_main(arguments):
    from app.services import asset_query_index as module
    original_error = module.AssetQueryUnavailable.__init__

    def observe_error(self):
        exception = sys.exc_info()[1]
        print('DIAGNOSTIC_INDEX_UNAVAILABLE', type(exception).__name__, repr(exception),
              'WINERROR', ctypes.get_last_error(), flush=True)
        if exception:
            traceback.print_exception(type(exception), exception, exception.__traceback__)
        else:
            traceback.print_stack(limit=6)
        original_error(self)

    module.AssetQueryUnavailable.__init__ = observe_error
    return original_main(arguments)

pytest.main = observed_main
raise SystemExit(runpy.run_path(str(Path.cwd() / 'scripts/run_studio_backend_tests.py'))['main']())
