from pathlib import Path

from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy

from songwriter_graph.api.api import ns
from songwriter_graph.api.ns import neighbors
from songwriter_graph.db.utils import read_config

CONFIG = read_config("/Users/jonjohnson/dev/swg/Song_Index/songwriter_graph/config.json")

app = Flask(__name__)
app.config.from_mapping(CONFIG)
db = SQLAlchemy(app)
api = Api(
    app, 
    version="1.0", 
    title='Songwriter Graph API')
api.add_namespace(neighbors)
