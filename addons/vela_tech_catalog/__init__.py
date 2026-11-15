from . import loader


def post_init_hook(env):
    loader.load_catalog(env)
