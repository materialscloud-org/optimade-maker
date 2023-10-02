# Materials Cloud Archive OPTIMADE integration

Users can now specify that their Materials Cloud Archive (MCA) submissions be
hosted with an [OPTIMADE API](https://optimade.org), allowing structural data
(and otherwise) to be queried by OPTIMADE clients.
This makes any structural data more discoverable, as structures and their
properties will be returned alongside queries to other major [data
providers](https://www.optimade.org/providers-dashboard/), and additionally
enables future programmatic re-use of the data.
This approach has already found use in select cases where AiiDA graphs were
exported and stored by MCA, and subsequently exposed with OPTIMADE APIs, but now
the functionality can be used on many common data types such as those understood
by [ASE](https://wiki.fysik.dtu.dk/ase/) and [pymatgen](https://pymatgen.org).

To enable this for an MCA submission, users must provide an additional config
file at the top-level of their submission, named `optimade.yml`.
The contents of this file will instruct the MCA data pipelines to ingest data
from supported formats, then create and expose a queryable database.
The full config file format, with examples, is described in the
[MCA-OPTIMADE integration GitHub repository](https://github.com/materialscloud-org/archive-optimade-integration/).

## Example

As a simple illustration of the functionality, let's say a user is submitting a
.zip file containing Crystallographic Information Files (CIF) describing the
outputs of some calculations, with a simple `.csv` file describing computed
properties of those crystals.

In this case, the config file first has to describe where the structural
data can be found, e.g.,:

```yaml
entries:
    - entry_type: structures
      entry_paths:
        - file: structures.zip
          matches:
            - structures/cifs/*.cif
```

Here, ASE will be used to parse the CIF files, and the
[optimade-python-tools](https://github.com/Materials-Consortia/optimade-python-tools)
library will be used to construct an OPTIMADE structure object.

The location of the computed properties can then be defined in a similar way (continuing the `entries->entry_type` block):

```yaml
entries:
  - entry_type: structures
    property_paths:
    - file:
      matches:
        - data/data.csv
        - data/data2.csv
```

Finally, definitions for the properties found in the `.csv` files can be
configured for enhanced sharing via OPTIMADE:

```yaml
entries:
  - entry_type: structures
    property_definitions:
        - name: energy
          title: Total energy per atom
          description: The total energy per atom as computed by GGA-DFT.
          unit: eV/atom
          type: float
```

which will enable database queries over these properties, and easier re-use by other scientists.

This full example, along with more complex examples, can be found on GitHub at [materialscloud-org/arcihve-optimade-integration](https://github.com/materialscloud-org/archive-optimade-integration/tree/main/src/mc_optimade/examples/folder_of_cifs).
