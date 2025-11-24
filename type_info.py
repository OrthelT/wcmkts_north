from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import requests
from logging_config import setup_logging
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
import json


logger = setup_logging(__name__)

sde_db_path = "sdelite2.db"
sde_db_url = f"sqlite+libsql:///sdelite2.db"
sde_db_engine = create_engine(sde_db_url)


@dataclass
class TypeInfo:
    """
    A dataclass representing EVE Online type information from the SDE database.
    
    This class can be initialized with either a type_id or type_name, and will automatically
    fetch all other type information from the database.
    
    Args:
        type_id: The EVE type ID (e.g., 34 for Tritanium). Either type_id or type_name required.
        type_name: The EVE type name (e.g., "Tritanium"). Either type_id or type_name required.
        
    Attributes:
        type_id: The EVE type ID (populated automatically if initialized with type_name).
        type_name: The EVE type name (populated automatically if initialized with type_id).
        group_name: The group name of the type (e.g., "Mineral").
        category_name: The category name of the type (e.g., "Material").
        category_id: The category ID of the type.
        group_id: The group ID of the type.
        volume: The volume of the type in m³.
        meta_group_id: The meta group ID of the type (e.g., 4 for Faction).
        meta_group_name: The meta group name of the type (e.g., "Faction").
        
    Raises:
        ValueError: If neither type_id nor type_name is provided, or if both are provided.
        
    Examples:
        >>> # Initialize with type ID
        >>> trit = TypeInfo(type_id=34)
        >>> print(trit.type_name)
        'Tritanium'
        
        >>> # Initialize with type name
        >>> trit2 = TypeInfo(type_name="Tritanium")
        >>> print(trit2.type_id)
        34
        
        >>> # After initialization, both identifiers are available
        >>> trit3 = TypeInfo(type_id=34)
        >>> print(f"ID: {trit3.type_id}, Name: {trit3.type_name}")
        ID: 34, Name: Tritanium
    """
    type_id: Optional[int] = field(default=None)
    type_name: Optional[str] = field(default=None)
    group_name: str = field(init=False)
    category_name: str = field(init=False)
    category_id: int = field(init=False)
    group_id: int = field(init=False)
    volume: float = field(init=False)
    meta_group_id: int = field(init=False, default=None)
    meta_group_name: str = field(init=False, default=None)
    packaged_volume: float = field(init=False, default=None)
    def __post_init__(self):
        """Validate input and populate all fields from the database."""
        # Validate that at least one identifier is provided
        if self.type_id is None and self.type_name is None:
            raise ValueError("Either type_id or type_name must be provided")
        
        if self.type_id is not None and self.type_name is not None:
            raise ValueError("Please provide either type_id or type_name, not both")
        
        self.get_type_info()
        self.packaged_volume = get_packaged_volume_from_esi(self.type_id)

    def get_type_info(self):
        """
        Query the SDE database to populate all type information fields.
        
        Builds the appropriate SQL query based on whether type_id or type_name was provided,
        then populates all attributes including the missing identifier.
        """
        engine = sde_db_engine
        
        # Build query based on which identifier was provided
        if self.type_id is not None:
            stmt = text("SELECT * FROM sdetypes WHERE typeID = :identifier")
            params = {"identifier": self.type_id}
        else:
            stmt = text("SELECT * FROM sdetypes WHERE typeName = :identifier")
            params = {"identifier": self.type_name}
        
        with engine.connect() as conn:
            result = conn.execute(stmt, params)
            for row in result:
                self.type_id = row.typeID
                self.type_name = row.typeName
                self.group_name = row.groupName
                self.category_name = row.categoryName
                self.category_id = row.categoryID
                self.group_id = row.groupID
                self.volume = row.volume
                self.meta_group_id = row.metaGroupID
                self.meta_group_name = row.metaGroupName
        engine.dispose()

def get_packaged_volume_from_esi(type_id: int) -> float:
    url = f"https://esi.evetech.net/universe/types/{type_id}"

    headers = {
    "Accept-Language": "",
    "If-None-Match": "",
    "X-Compatibility-Date": "2025-09-30",
    "X-Tenant": "",
    "Accept": "application/json",
    "User-Agent": "WC markets v0.52 (admin contact: Orthel.Toralen@gmail.com; +https://github.com/OrthelT/wcmkts_new)",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data['packaged_volume']
    else:
        logger.error(f"Error fetching: {response.status_code}")
        raise Exception(f"Error fetching packaged volume for {type_id}: {response.status_code}")


def get_type_name(type_id: int) -> str:
    # Prefer sde_lite.db; fall back to sde.db if present
    stmt  = text("SELECT typeName FROM invTypes as it WHERE it.typeID = :type_id")
    df = pd.read_sql_query(stmt, sde_db_engine, params={"type_id": type_id})
    if df.empty:
        return None
    return df['typeName'].iloc[0]

def get_type_id_from_sde(type_name: str) -> int:
    stmt = text("SELECT typeID FROM invTypes as it WHERE it.typeName = :type_name")
    df = pd.read_sql_query(stmt, sde_db_engine, params={"type_name": type_name})
    if df.empty:
        return None
    return df['typeID'].iloc[0]

def get_type_id_from_fuzzworks(type_name: str) -> int:
    url = f"https://www.fuzzwork.co.uk/api/typeid.php?typename={type_name}"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        return int(data["typeID"])
    else:
        logger.error(f"Error fetching: {response.status_code}")
        raise Exception(f"Error fetching type id for {type_name}: {response.status_code}")

def get_backup_type_id(type_name: str) -> int:
    type_id = get_type_id_from_sde(type_name)
    if type_id:
        logger.debug(f"SDE found type_id for {type_name}: {type_id}")
    else:
        type_id = get_type_id_from_fuzzworks(type_name)
        if type_id:
            logger.debug(f"Fuzzwork found type_id for {type_name}: {type_id}")
        else:
            logger.error(f"No type_id found for {type_name}")
            type_id = None
    return type_id

if __name__ == "__main__":
    pass