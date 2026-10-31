def pytest_runtest_call(item):
    if 'keyed' in item.funcargs:
        item.funcargs['keyed'].client._transport.raise_server_exceptions = True
