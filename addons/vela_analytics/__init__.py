from . import controllers, models, services


def post_init_hook(env):
    # Random per-database salt for visitor hashes (plan §4). Never in git.
    env["vela.analytics.event"]._visitor_salt()
