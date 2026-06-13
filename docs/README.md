# MS Monitoring Docs

This directory contains the project documentation in formats intended for
different publication targets:

- `README.md`: landing page shown when browsing `docs/` on GitHub
- `index.md`: landing page for GitHub Pages when the site is published from
  `/docs`
- `index.rst`: Sphinx entry point used to build the full Read the Docs site

## Documentation entry points

- GitHub folder view: [README.md](./README.md)
- GitHub Pages: [index.md](./index.md)
- Sphinx source: [index.rst](./index.rst)
- Read the Docs build config: [../.readthedocs.yaml](../.readthedocs.yaml)

## Read the Docs

The complete technical documentation is built with Sphinx from `index.rst`
using `docs/conf.py`.

## Local build

```bash
pip install -r docs/requirements.txt
cd docs
make html
```

The generated HTML site will be available at `_build/html/index.html`.
