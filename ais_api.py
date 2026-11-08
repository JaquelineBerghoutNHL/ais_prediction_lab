import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://aisdatabase.serverict.nl"

headers = {
    "X-API-Key": os.getenv("AIS_API_KEY")
}


def zoek_schepen(naam):
    response = requests.get(
        f"{BASE_URL}/ships",
        headers=headers,
        params={"name_contains": naam, "limit": 20},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def haal_posities_op(mmsi, offset=0, limit=1000):
    response = requests.get(
        f"{BASE_URL}/ships/{mmsi}/positions",
        headers=headers,
        params={
            "limit": limit,
            "offset": offset,
            "order": "asc"
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()
