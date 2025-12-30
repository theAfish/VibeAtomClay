from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import tempfile
import os
import logging
import numpy as np
from pymatgen.core import Structure
from pymatgen.core.interface import fix_pbc
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.interfaces import SubstrateAnalyzer, CoherentInterfaceBuilder

router = APIRouter(
    prefix="/materials",
    tags=["materials"]
)

logger = logging.getLogger(__name__)

class StructureData(BaseModel):
    structure_string: str
    format: str = "poscar"  # cif, poscar, json

@router.post("/analyze")
async def analyze_structure(data: StructureData):
    """
    Analyze a structure using Pymatgen locally.
    Returns symmetry, chemical formula, and other basic properties.
    """
    try:
        # Load structure
        if data.format.lower() == "cif":
            structure = Structure.from_str(data.structure_string, fmt="cif")
        elif data.format.lower() == "poscar":
            structure = Structure.from_str(data.structure_string, fmt="poscar")
        elif data.format.lower() == "json":
            import json
            d = json.loads(data.structure_string)
            structure = Structure.from_dict(d)
        else:
            # Fallback to auto-detect if possible or default to CIF
            structure = Structure.from_str(data.structure_string, fmt="cif")

        # Analyze
        sga = SpacegroupAnalyzer(structure)
        symmetry = sga.get_symmetry_dataset()
        
        return {
            "formula": structure.composition.reduced_formula,
            "num_sites": structure.num_sites,
            "volume": structure.volume,
            "density": structure.density,
            "is_ordered": structure.is_ordered,
            "symmetry": {
                "symbol": symmetry["international"],
                "number": symmetry["number"],
                "hall": symmetry["hall"]
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing structure: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Analysis failed: {str(e)}")

@router.post("/parse")
async def parse_structure(data: StructureData):
    """
    Parse a structure and return atoms and lattice for visualization.
    Replaces frontend CIF parsing.
    """
    try:
        # Load structure
        if data.format.lower() == "cif":
            structure = Structure.from_str(data.structure_string, fmt="cif")
        elif data.format.lower() == "poscar":
            structure = Structure.from_str(data.structure_string, fmt="poscar")
        elif data.format.lower() == "json":
            import json
            d = json.loads(data.structure_string)
            structure = Structure.from_dict(d)
        else:
            # Fallback to auto-detect if possible or default to CIF
            structure = Structure.from_str(data.structure_string, fmt="cif")

        # Extract data for frontend
        lattice = structure.lattice.matrix.tolist()
        atoms = []
        for site in structure:
            try:
                element = site.specie.symbol
            except:
                # For disordered structures, take the element with highest occupancy
                element = site.species.most_common(1)[0][0].symbol

            atoms.append({
                "element": element,
                "x": site.x,
                "y": site.y,
                "z": site.z
            })
            
        return {
            "atoms": atoms,
            "lattice": lattice
        }

    except Exception as e:
        logger.error(f"Error parsing structure: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Parsing failed: {str(e)}")

@router.post("/convert")
async def convert_structure(data: StructureData, target_format: str = "cif"):
    """
    Convert structure format locally.
    """
    try:
        # Load (reuse logic or refactor)
        if data.format.lower() == "cif":
            structure = Structure.from_str(data.structure_string, fmt="cif")
        elif data.format.lower() == "poscar":
            structure = Structure.from_str(data.structure_string, fmt="poscar")
        else:
            structure = Structure.from_str(data.structure_string, fmt="cif")

        if target_format.lower() == "cif":
            return {"structure_string": structure.to(fmt="cif"), "format": "cif"}
        elif target_format.lower() == "poscar":
            return {"structure_string": structure.to(fmt="poscar"), "format": "poscar"}
        elif target_format.lower() == "json":
            return {"structure_string": structure.to_json(), "format": "json"}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported target format: {target_format}")

    except Exception as e:
        logger.error(f"Error converting structure: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Conversion failed: {str(e)}")



class BuildInterfaceRequest(BaseModel):
    film_structure_string: str
    film_format: str = "poscar"
    substrate_structure_string: str
    substrate_format: str = "poscar"
    film_miller: Optional[list] = [1, 0, 0]
    substrate_miller: Optional[list] = [1, 1, 1]
    max_area: Optional[float] = 400.0
    max_length_tol: Optional[float] = 0.03
    max_angle_tol: Optional[float] = 0.01
    gap: float = 2.5
    vacuum_over_film: Optional[float] = 0.0
    film_thickness: int = 2
    substrate_thickness: int = 2
    in_layers: Optional[bool] = True
    max_interfaces: int = 60


@router.post("/build_interfaces")
async def build_interfaces(data: BuildInterfaceRequest):
    """
    Build multiple interface candidates between film and substrate and return them
    as serializable dicts for frontend selection.
    """
    try:
        def _parse_struct(s: str, fmt: str) -> Structure:
            if fmt.lower() == "cif":
                return Structure.from_str(s, fmt="cif")
            elif fmt.lower() == "poscar":
                return Structure.from_str(s, fmt="poscar")
            elif fmt.lower() == "json":
                import json
                return Structure.from_dict(json.loads(s))
            else:
                return Structure.from_str(s, fmt=fmt)

        # first get conventional cells for both structures
        film_structure = _parse_struct(data.film_structure_string, data.film_format).to_conventional()
        substrate_structure = _parse_struct(data.substrate_structure_string, data.substrate_format).to_conventional()

        cib = CoherentInterfaceBuilder(
            substrate_structure=substrate_structure,
            film_structure=film_structure,
            film_miller=tuple(data.film_miller),
            substrate_miller=tuple(data.substrate_miller)
        )

        results = []
        collected = 0
        for t_idx, termination in enumerate(cib.terminations):
            interfaces = list(cib.get_interfaces(
                termination=termination,
                gap=data.gap,
                vacuum_over_film=(data.vacuum_over_film if data.vacuum_over_film != 0 else data.gap),
                film_thickness=data.film_thickness,
                substrate_thickness=data.substrate_thickness,
                in_layers=data.in_layers
            ))

            
            for iface_idx, interface in enumerate(interfaces):
                wraped_iface = fix_pbc(interface)
                atoms = []
                for site in wraped_iface:
                    try:
                        element = site.specie.symbol
                    except Exception:
                        element = site.species.most_common(1)[0][0].symbol
                    atoms.append({"element": element, "x": site.x, "y": site.y, "z": site.z})

                lattice = interface.lattice.matrix.tolist() if interface.lattice is not None else None

                # Calculate area (magnitude of cross product of first two lattice vectors)
                
                vec_a = interface.lattice.matrix[0]
                vec_b = interface.lattice.matrix[1]
                area = float(np.linalg.norm(np.cross(vec_a, vec_b)))

                iface_dict = {
                    "id": f"iface_{collected}",
                    "von_mises_strain": interface.interface_properties["von_mises_strain"],
                    "termination_index": t_idx,
                    "interface_index": iface_idx,
                    "atoms": atoms,
                    "lattice": lattice,
                    "area": area,
                }

                # include CIF text representation for convenient download/display
                try:
                    iface_dict["poscar"] = wraped_iface.to(fmt="poscar")
                except Exception:
                    # If conversion to CIF fails, skip adding the text form
                    iface_dict["poscar"] = None

                results.append(iface_dict)
                collected += 1
                if collected >= data.max_interfaces:
                    break
            if collected >= data.max_interfaces:
                break
        return {"interfaces": results}  
    except Exception as e:
        logger.error(f"Error building interfaces: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Interface building failed: {str(e)}")
