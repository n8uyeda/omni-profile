# NOTICE

This project's own source code (the profile engine and viewer under `tools/`)
is licensed under the MIT License — see `LICENSE`.

It depends on third-party libraries that carry their own license terms.

## Swiss Ephemeris (via pyswisseph)

`tools/profile-engine/` imports the [pyswisseph](https://github.com/astrorigin/pyswisseph)
Python bindings, which wrap the **Swiss Ephemeris** library by Astrodienst AG.

Swiss Ephemeris is distributed under two licenses, at the user's choice:

1. **AGPL-3.0** (GNU Affero General Public License v3) — free to use, but
   network-served use requires source disclosure to users of the service.
2. **Swiss Ephemeris Professional License** — commercial license available
   from Astrodienst AG for use in proprietary or closed-source contexts.
   Contact <https://www.astro.com/swisseph/> for terms.

Because this project's deployed form (Vercel-hosted web app) makes the
ephemeris computations available over a network, the AGPL-3.0 disclosure
requirement applies to the combined work. The MIT-licensed engine code in
`tools/profile-engine/` is the disclosure: its source is published in this
public repository.

If you fork this project for proprietary or closed-source commercial use,
you must obtain a Professional License from Astrodienst AG.

## PyYAML

`tools/profile-engine/` and `tools/profile-viewer/` both use
[PyYAML](https://pyyaml.org/), distributed under the MIT License.

## Jinja2

`tools/profile-viewer/` uses [Jinja2](https://palletsprojects.com/p/jinja/),
distributed under the BSD-3-Clause License.

---

*Project authored by Nathan Uyeda (N8). Built on top of the
[Creator System](https://themostfamousartist.com) architecture by Matty Mo
Studio.*
