<div align="center" style="padding: 2em;">
<span style="padding: 1em">
<img height="70px" align="center" src="https://matsci.org/uploads/default/original/2X/b/bd2f59b3bf14fb046b74538750699d7da4c19ac1.svg">
</span>
</div>

# <div align="center">optimade-maker</div>

<div align="center">

[![PyPI - Version](https://img.shields.io/pypi/v/optimade-maker?color=4CC61E)](https://pypi.org/project/optimade-maker/)
![PyPI - License](https://img.shields.io/pypi/l/optimade-maker?color=blue)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/materialscloud-org/optimade-maker/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18863676.svg)](https://doi.org/10.5281/zenodo.18863676)
[![Paper DOI](https://img.shields.io/badge/Paper-10.1039%2FD6DD00125D-blue)](https://doi.org/10.1039/D6DD00125D)

</div>

Tools for making [OPTIMADE APIs](https://optimade.org) from various formats of structural data (e.g. an archive of CIF files).

This repository contains the src/optimade-maker Python package and the corresponding CLI tool optimake, which together provide this functionality. Features include

- definition of a config file format (`optimade.yaml`) for annotating data archives to be used in the OPTIMADE ecosystem;
- conversion of the raw data into corresponding OPTIMADE types using pre-existing parsers (e.g., ASE for structures);
- conversion of the annotated data archive into the OPTIMADE JSON Lines file format ([spec](https://github.com/Materials-Consortia/OPTIMADE/blob/develop/optimade.rst#the-optimade-json-lines-format-for-database-exchange)) that can be ingested into a database and used to serve a full OPTIMADE API.
- serving either an annotated data archive or a JSON Lines file as an OPTIMADE API (using the [`optimade-python-tools`](https://github.com/Materials-Consortia/optimade-python-tools/)
  reference server implementation).

## Installation and usage

Install with

```bash
pip install optimade-maker
# or to get all ingestion plugins (e.g. pymatgen, aiida):
pip install optimade-maker[ingest]
```

this will also make the `optimake` CLI utility available.

For a folder containing the data archive and the `optimade.yaml` file (such as in `/examples`), run

- `optimake convert .` to convert the entry into the JSONL format (see below).
- `optimake serve .` to start the OPTIMADE API (this also converts the entry, if needed);

For more detailed information, see `optimake --help`.

### Tutorial

The sections below provide a high-level overview of the functionality, but a step-by-step notebook tutorial is available in `examples/00_tutorial/tutorial.ipynb`, demonstrating the full workflow from raw data to a running OPTIMADE API and example queries.

To run the tutorial locally, install `optimade-maker[tutorial]` and open the notebook with Jupyter.

### Annotating with `optimade.yaml`

To annotate your structural data for `optimade-maker`, the data archive needs to be accompanied by an `optimade.yaml` config file. The following is a simple example for a ZIP archive (`structures.zip`) of CIF files together with an optional property file (`properties.csv`):

```yaml
config_version: 0.2.0
database_description: Simple DB

entries:
  - entry_type: structures
    entry_paths:
      - path: structures.zip
        matches:
          - cifs/*/*.cif
    # (optional) properties:
    property_paths:
      - path: properties.csv
    property_definitions:
      - name: energy
        title: Total energy
        description: DFT total energy
        unit: eV/atom
        type: float
```

See `./examples` for a more complete set of supported formats and corresponding `optimade.yaml` config files.

### Structure `id`s and property files

`optimade-maker` will assign an `id` for each structure based on its full path in the archive, following a simple deterministic rule: from the set of all archive paths, the maximum common path prefix and postfix (including file extensions) are removed. E.g.

```
structures.zip/cifs/set1/101.cif
structures.zip/cifs/set2/102.cif
```

produces `["set1/101", "set2/102"]`.

The property files need to either refer to these `id`s or the full path in the archive to be associated with a structure. E.g. a possible property `csv` file could be

```csv
id,energy
set1/101,2.5
structures.zip/cifs/set2/102.cif,3.2
```

### Usage in a custom data pipeline

The toolkit supports a custom data pipeline (e.g. with an external MongoDB), by allowing to override any of the configuration passed to `optimade-python-tools`. See `./examples/override_config` for details.

## Relevant links

- [OPTIMADE specification](https://github.com/Materials-Consortia/OPTIMADE/blob/develop/optimade.rst)
- [OPTIMADE specification: JSON Lines format](https://github.com/Materials-Consortia/OPTIMADE/blob/develop/optimade.rst#the-optimade-json-lines-format-for-database-exchange)

## Citation

If you use `optimade-maker` in your research, please cite:

> K. Eimre, M. L. Evans, B. Macaulay, X. Wang, J. Yu, N. Marzari, G.-M. Rignanese, and G. Pizzi, optimade-maker: Automated generation of interoperable materials APIs from static datasets, Digital Discovery (2026). DOI: [10.1039/D6DD00125D](https://doi.org/10.1039/D6DD00125D)

Preprint: https://doi.org/10.48550/arXiv.2603.23536

## For developers

### Releasing a new version

This project uses `setuptools_scm`, which reads the version from git tags. To release a new version:

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push --tags
```

This will trigger the Github Action that will create 1) a Github release; and 2) build and publish the package on pypi.

## Acknowledgements

This project was funded by the NCCR MARVEL, a National Centre of Competence in Research, funded by the Swiss National Science Foundation (grant number 205602).
We also acknowledge support by the Open Research Data Program of the Swiss ETH Board (project "API-03 IntER").
