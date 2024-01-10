<div align="center" style="padding: 2em;">
<span style="padding: 1em">
<img height="70px" align="center" src="https://matsci.org/uploads/default/original/2X/b/bd2f59b3bf14fb046b74538750699d7da4c19ac1.svg">
</span>
</div>


# <div align="center">optimade-maker</div>

Code for making [OPTIMADE APIs](https://optimade.org) from various formats of structural data (e.g. an archive of CIF files).

This repository contains the following Python packages that work towards this
aim:

- `src/mc_optimade`: defines a config file format for annotating archives and registered the desired OPTIMADE entries, and a workflow for ingesting them and converting into OPTIMADE types using pre-existing parsers (e.g., ASE for structures). The archive is converted into an intermediate [OPTIMADE JSON Lines](https://github.com/Materials-Consortia/OPTIMADE/issues/471) format that can be ingested into a database and used to serve a full OPTIMADE API.
- `src/optimade_launch`: provides a platform for launching an OPTIMADE API server
from such a JSON lines file. It does so using the
[`optimade-python-tools`](https://github.com/Materials-Consortia/optimade-python-tools/)
reference server implementation.

## Usage

To generate an [OPTIMADE JSON Lines](https://github.com/Materials-Consortia/OPTIMADE/issues/471) file, the structural data needs to be accompanied by an `optimade.yaml` config file. A minimal example for a zip archive (`structures.zip`) of cif files is the following:

```
entries:
  - entry_type: structures
    entry_paths:
      - file: structures.zip
        matches:
          - structures/cifs/*.cif
```

Run `optimake .` in the folder containing `structures.zip` and `optimade.yaml` to generate the jsonl file.

See `src/mc_optimade/examples` for other supported formats and corresponding `optimade.yaml` config files.


## Relevant links

- [Roadmap and meeting notes](https://docs.google.com/document/d/1cIpwuX6Ty5d3ZHKYWktQaBBQcI9fYmgG_hsD1P1UpO4/edit)
- [OPTIMADE serialization format notes](https://docs.google.com/document/d/1vf8_qxSRP5lCSb0P3M9gTr6nqkERxgOoSDno6YLcCjo/edit)
- [Flow diagram](https://excalidraw.com/#json=MBNl66sARCQekVrKZXDg8,K35f5FwmiS46vlsYGMJdrw)

## Contributors

Initial prototype was created at the Paul Scherrer Institute, Switzerland in the week of
12th-16th June 2023.

Authors (alphabetical):

- Kristjan Eimre
- Matthew Evans
- Giovanni Pizzi
- Jusong Yu
- Xing Wang
