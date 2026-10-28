"""Shared CNMC transport preserves electricity JSON scalar types."""

import io
import json
from typing import ClassVar

from electricity_map_ingestion import cnmc_client


def test_datastore_numbers_remain_json_serializable(monkeypatch):
    body = b'{"success":true,"result":{"total":1,"records":[{"_id":1,"value":900719925474.09991}]}}'

    class Response(io.BytesIO):
        status = 200
        headers: ClassVar = {"Content-Type": "application/json", "Content-Length": str(len(body))}

    monkeypatch.setattr(cnmc_client.urllib.request, "urlopen", lambda *args, **kwargs: Response(body))
    monkeypatch.setattr(cnmc_client.time, "sleep", lambda _: None)
    electricity = list(cnmc_client.online_rows("resource"))
    assert isinstance(electricity[0]["value"], float)
    assert json.loads(json.dumps(electricity)) == electricity
