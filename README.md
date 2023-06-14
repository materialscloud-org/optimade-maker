# archive-optimade-integration

Scripts and data related to the integration of the Materials Cloud Archive and OPTIMADE.

## How to use optimade-launch

`optimade-launch` is the cli tool to start a optimade server from `JSONL` database easily.

To use OPTIMADE launch you will have to

1. [Install Docker on your workstation or laptop.](https://docs.docker.com/get-docker/)
2. Install OPTIMADE launch with [pipx](https://pypa.github.io/pipx/installation/) (**recommended**):

   ```console
   pipx install optimade-launch
   ```

   _Or directly with pip (`pip install optimade-launch`)._

3. creating a profile and attach a database from inject data from JSONL file

   ```console
   optimade-launch profile create --profile-name test --jsonl-file /path/to/your/jsonl/file
   ```

4. Start OPTIMADE server of testing data with

    ```console
    optimade-launch start
    ```
5. Follow the instructions on screen to open OPTIMADE API in the browser.

See `optimade-launch --help` for detailed help.

### Instance Management

You can inspect the status of all configured AiiDAlab profiles with:

```console
optimade-launch status
```

### Profile Management

The tool allows to manage multiple profiles, e.g., with different home directories or ports.
See `optimade-launch profile --help` for more information.

## Relevant links

- [Roadmap and meeting notes](https://docs.google.com/document/d/1cIpwuX6Ty5d3ZHKYWktQaBBQcI9fYmgG_hsD1P1UpO4/edit)
- [OPTIMADE serialization format notes](https://docs.google.com/document/d/1vf8_qxSRP5lCSb0P3M9gTr6nqkERxgOoSDno6YLcCjo/edit)
- [Flow diagram](https://excalidraw.com/#json=MBNl66sARCQekVrKZXDg8,K35f5FwmiS46vlsYGMJdrw)
