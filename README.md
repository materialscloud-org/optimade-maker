<div align="center" style="padding: 2em;">
<span style="padding: 1em">
<img height="70px" align="center" src="https://matsci.org/uploads/default/original/2X/b/bd2f59b3bf14fb046b74538750699d7da4c19ac1.svg">
</span>
<span style="padding: 1em">
<img height="70px" align="center" src="https://raw.githubusercontent.com/materialscloud-org/discover-mc3d-react/main/public/mcloud_spinner.svg">
</span>
</div>


# <div align="center">archive-optimade-integration</div>

Code and data related to the integration of the Materials Cloud Archive (MCA) and OPTIMADE.
The aim is to provide a way for MCA users to create archives that can ingested
and hosted as [OPTIMADE APIs](https://optimade.org), enabling enhanced data discoverability and
explorability.

This prototype repository contains two Python packages that work towards this
aim.

- `mc_optimade`: defines a config file format for annotating archives and registered the desired OPTIMADE entries, and a workflow for ingesting them and converting into OPTIMADE types using pre-existing parsers (e.g., ASE for structures). The archive is converted into an intermediate [OPTIMADE JSON Lines](https://github.com/Materials-Consortia/OPTIMADE/issues/471#issuecomment-1589274856) format that can be ingested into a database and used to serve a full OPTIMADE API.
- `optimade_launch`: provides a platform for launching an OPTIMADE API server
from such a JSON lines file. It does so using the
[`optimade-python-tools`](https://github.com/Materials-Consortia/optimade-python-tools/)
reference server implementation.

## Relevant links

- [Roadmap and meeting notes](https://docs.google.com/document/d/1cIpwuX6Ty5d3ZHKYWktQaBBQcI9fYmgG_hsD1P1UpO4/edit)
- [OPTIMADE serialization format notes](https://docs.google.com/document/d/1vf8_qxSRP5lCSb0P3M9gTr6nqkERxgOoSDno6YLcCjo/edit)
- [Flow diagram](https://excalidraw.com/#json=MBNl66sARCQekVrKZXDg8,K35f5FwmiS46vlsYGMJdrw)

## Contributors

This prototype was created at the Paul Scherrer Institute, Switzerland in the week of
12th-16th June 2023.

Authors (alphabetical):

- Kristjan Eimre
- Matthew Evans
- Giovanni Pizzi
- Jusong Yu
- Xing Wang
