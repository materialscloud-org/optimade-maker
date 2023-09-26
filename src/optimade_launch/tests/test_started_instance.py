import pytest 
import re

# start a instance and test real actions
@pytest.mark.usefixtures("started_instance")
class TestsAgainstStartedInstance:
    
    @pytest.mark.asyncio
    async def test_instance_status(self, started_instance):
        assert (
            await started_instance.status()
            is started_instance.OptimadeInstanceStatus.UP
        )
        
    def test_instance_url(self, started_instance):
        assert re.match(
            r"http:\/\/localhost:\d+\/", started_instance.url()
        )
    
    def test_instance_host_ports(self, started_instance):
        assert len(started_instance.host_ports()) > 0
        
    @pytest.mark.asyncio
    async def test_instance_query(self, started_instance):
        """make a query to the instance"""
        import requests
        assert (
            await started_instance.status()
            is started_instance.OptimadeInstanceStatus.UP
        )
        
        response = requests.get(started_instance.url() + "v1/structures")
        assert response.status_code == 200
        assert response.json()["meta"]["data_available"] == 3