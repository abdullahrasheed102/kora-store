"""Products, categories and policies: the public catalog.

GET /api/products            list with filters, search, sort and pagination
GET /api/products/<slug>     one product with variants and live stock
GET /api/categories          categories with product counts
GET /api/policies            all store policies
GET /api/policies/<key>      one policy
"""

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from app import catalog
from app.catalog import ProductListQuery
from app.extensions import db
from app.validation import parse_query

bp = Blueprint("products", __name__)


@bp.get("/products")
def list_products() -> ResponseReturnValue:
    query = parse_query(ProductListQuery, request.args)
    return catalog.list_products(db.session, query)


@bp.get("/products/<slug>")
def get_product(slug: str) -> ResponseReturnValue:
    return catalog.get_product(db.session, slug)


@bp.get("/categories")
def list_categories() -> ResponseReturnValue:
    return jsonify(catalog.list_categories(db.session))  # jsonify: a top-level list isn't auto-converted


@bp.get("/policies")
def list_policies() -> ResponseReturnValue:
    return jsonify(catalog.list_policies(db.session))


@bp.get("/policies/<key>")
def get_policy(key: str) -> ResponseReturnValue:
    return catalog.get_policy(db.session, key)
