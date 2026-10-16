"""Synthetic, offline host example. No arbitrary package or model is loaded."""
from app.experimental.declarative_adapter_sdk import AdapterRequest, LocalRecipeAdapter, run_trusted_local


def example():
    # Production hosts must supply current session/scope/source/feature checks.
    # This isolated example handles only explicit public synthetic text.
    request = AdapterRequest('draft_prepare', {'source_text': '林舟等潮落。\n同伴举起合成地图。'},
                             'synthetic-example', 'synthetic-public-scope')
    return run_trusted_local(LocalRecipeAdapter(), request, authorize=lambda: None)


if __name__ == '__main__':
    result = example()
    print(result.output)
