"""All HTTP routes. One blueprint per area of the API, all mounted under /api."""

from flask import Flask

from app.api import admin, agent, auth, cart, checkout, email, health, newsletter, orders, products

BLUEPRINTS = (
    health.bp,
    auth.bp,
    products.bp,
    cart.bp,
    checkout.bp,
    orders.bp,
    newsletter.bp,
    email.bp,
    admin.bp,
    agent.bp,
)


def register_blueprints(app: Flask) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix="/api")
