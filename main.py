from typing import Union
from typing import Annotated


from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlmodel import Field, SQLModel, create_engine, Session, select


import json
from glob import glob
from pathlib import Path


# sites
# node_types
# nodes



class Node(SQLModel, table=True):
    uuid: str = Field(primary_key=True)
    node_name: str
    node_type: str
    site: str
        
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def populate_db_from_json():
    with Session(engine) as session:
        for nodefile in glob('reference-repository/data/chameleoncloud/sites/*/clusters/chameleon/nodes/*.json'):
            filepath = Path(nodefile)
            parts=filepath.parts
            site = parts[4]
            with open(nodefile, "r") as f:
                data = json.load(f)
            node = Node(
                    uuid=data.get("uid"),
                    node_name=data.get("node_name"),
                    node_type=data.get("node_type"),
                    site=site,
                    )
            try:
                session.add(node)
                session.commit()
            except Exception as ex:
                continue

  
app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    populate_db_from_json()

@app.get("/nodes")
def list_nodes(
	session: SessionDep,
    ):
    nodes = session.exec(
                        select(Node)
                        ).all()
    return nodes


@app.get("/nodes/{node_id}")
def read_node(node_id: str, session: SessionDep) -> Node:
    node = session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node
