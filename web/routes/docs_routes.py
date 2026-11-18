from flask import Blueprint,jsonify
from web.openapi_spec import build_openapi

docs_bp=Blueprint('api_docs',__name__)

@docs_bp.get('/openapi.json')
def openapi_document():
    return jsonify(build_openapi())
