from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import tempfile
import os
import logging
from pymatgen.core import Structure
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

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
