from fastapi.testclient import TestClient
from pymatgen.core import Lattice, Structure
import sys
import os
# Ensure local packages/middleware/app is importable during tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from middleware.app.main import app

client = TestClient(app)


def test_build_interfaces_basic():
    """Sanity check: POST to /materials/build_interfaces returns a JSON with 'interfaces'"""
    lat = Lattice.cubic(3.5)
    film = Structure(lat, ["Fe"], [[0, 0, 0]])
    substrate = Structure(lat, ["Fe"], [[0, 0, 0]])

    payload = {
        "film_structure_string": film.to(fmt="poscar"),
        "film_format": "poscar",
        "substrate_structure_string": substrate.to(fmt="poscar"),
        "substrate_format": "poscar",
        "film_miller": [1, 0, 0],
        "substrate_miller": [1, 0, 0],
        "max_interfaces": 2,
    }

    resp = client.post("/materials/build_interfaces", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "interfaces" in data
    assert isinstance(data["interfaces"], list)
