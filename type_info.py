from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import os
import requests
from logging_config import setup_logging
import pandas as pd

logger = setup_logging(__name__)

sde_db_path = "sdelite.db"
sde_db_url = f"sqlite+libsql:///sdelite.db"
sde_db_engine = create_engine(sde_db_url)

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