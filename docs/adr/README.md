# Architecture decisions

| # | Decision | Status |
|---|---|---|
| [0001](0001-monorepo-with-odoo-image.md) | One monorepo; Odoo source stays in the Docker image | accepted |
| [0002](0002-catalog-as-json-loader-addon.md) | Demo catalog as JSON + idempotent loader addon, real freely-licensed images | accepted |
| [0003](0003-custom-theme-addon.md) | Custom `theme_vela` addon instead of a stock theme + builder clicks | accepted |
| [0004](0004-identical-environments-from-git.md) | Identical environments from git: pinned images, `vela_setup`, setup/update/drift scripts | accepted |
| [0005](0005-theme-as-regular-addon.md) | Theme is a regular addon `vela_theme`, not a `theme_*` module | accepted |
| [0006](0006-motion-libraries.md) | Motion: vendored GSAP 3.12.5 + ScrollTrigger and Lenis 1.1.13 as Odoo Interactions | accepted |
| [0007](0007-tracking-areas-v1.md) | Tracking areas consent, recommend, carousel, empty, configurator, auto-fallback | accepted |
