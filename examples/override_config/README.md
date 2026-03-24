# Config overriding

This example showcases how to override the config that gets passed to `optimade-python-tools`.

See [here](https://www.optimade.org/optimade-python-tools/1.4.1/configuration/) what configuration options are supported.

One can override the config options by creating env variable starting with `OPTIMAKE_`, or passing a json file to `serve` command, e.g. by:

```bash
> optimake serve --override_config_file override_config.json .
```

Note that some configuration options are automatically detected and populated by `optimade-maker`, and these should not be overridden. These include

- `provider_fields`
- `aliases`

Here is a list of commonly overridden configuration options (e.g. in a data pipeline):

- `"database_backend": "mongodb",` - for an external MongoDB instead of MongoMock.
- `"mongo_uri": ...,`
- `"mongo_database": ...,`
- `"provider": {...},` - custom provider instead of the default "\_optimake".
