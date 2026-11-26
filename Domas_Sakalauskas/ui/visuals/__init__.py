"""Visuals registry: every .py file in this folder that defines NAME, settings() and render() is a visual.

To add a visual: copy shot_map.py, rename it, change NAME / settings / render. Nothing else to edit.
"""
import importlib
import pkgutil

NOT_VISUALS = {"theme", "data"}


def discover():
    """Returns (visuals, errors): visuals = {NAME: module}, errors = {module name: message}."""
    visuals, errors = {}, {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_") or info.name in NOT_VISUALS:
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{info.name}")
            importlib.reload(mod)  # pick up edits without restarting Streamlit
        except Exception as exc:  # one broken visual must not break the others
            errors[info.name] = f"{type(exc).__name__}: {exc}"
            continue
        if all(hasattr(mod, a) for a in ("NAME", "settings", "render")):
            visuals[mod.NAME] = mod
    return dict(sorted(visuals.items())), errors