from pydantic import BaseSettings

class MCOptimadeSettings(BaseSettings):
    """This class describes the `optimade.yaml` file
    that a user can provide for each MCloud entry.

    """

    entries: 
