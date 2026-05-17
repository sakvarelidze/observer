class MonitorType:
    name: str = "base"
    supports_conditions: bool = False
    condition_variables = []

    async def check(self, monitor, heartbeat, server=None):
        raise NotImplementedError
