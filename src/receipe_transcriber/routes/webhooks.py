from flask import Blueprint

bp = Blueprint('webhooks', __name__)

# TODO: Something to ensure that only intended sources can hit these endpoints. 