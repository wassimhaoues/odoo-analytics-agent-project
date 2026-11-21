"""Trusted server events from the shop flow (plan §3, §7).

Each hook calls super() first and records after; recording never raises (see _emit_server).
"""
import json
import re

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.payment import PaymentPortal
from odoo.exceptions import UserError, ValidationError
from odoo.http import request, route


def _events():
    return request.env["vela.analytics.event"]


def _category_slug(category):
    if not category:
        return False
    slug = request.env["ir.http"]._slug(category)
    return re.sub(r"-\d+$", "", slug)[:64]


def _emit_failure(exc, order_id=None):
    code = "payment_rejected" if isinstance(exc, (UserError, ValidationError)) else "server_error"
    # own_cursor: the request transaction is about to roll back
    _events()._emit_server("checkout_error", own_cursor=True, error_code=code,
                           sale_order_id=order_id or False)


class VelaWebsiteSale(WebsiteSale):
    @route()
    def shop(self, page=0, category=None, search="", **post):
        response = super().shop(page=page, category=category, search=search, **post)
        qcontext = getattr(response, "qcontext", None)
        if search and qcontext and not page:  # first page only: paging isn't a new search
            _events()._emit_server(
                "search",
                search_results_count=int(qcontext.get("search_count") or 0),
                category=_category_slug(qcontext.get("category")),
            )
        return response

    @route()
    def shop_address_submit(self, *args, **kwargs):
        response = super().shop_address_submit(*args, **kwargs)
        try:
            feedback = json.loads(response.get_data())
        except (ValueError, AttributeError):
            feedback = {}
        if isinstance(feedback, dict) and feedback.get("invalid_fields"):
            fields_ = sorted(feedback["invalid_fields"])[:10]
            _events()._emit_server(
                "checkout_error", error_code="address_invalid",
                sale_order_id=request.cart.id or False,
                payload={"fields": [f for f in fields_ if re.match(r"^[a-z_]{1,40}$", f)]},
            )
        return response

    @route()
    def shop_payment_validate(self, *args, **kwargs):
        try:
            return super().shop_payment_validate(*args, **kwargs)
        except Exception as exc:
            _emit_failure(exc, request.session.get("sale_last_order_id"))
            raise


class VelaCart(Cart):
    @route()
    def add_to_cart(self, product_template_id, product_id, quantity, *args, **kwargs):
        values = super().add_to_cart(product_template_id, product_id, quantity, *args, **kwargs)
        order = request.cart
        product = request.env["product.product"].sudo().browse(int(product_id)).exists()
        sku, variant = _events()._sku_of(product)
        events = _events()._emit_server(
            "add_to_cart",
            product_id=product.id or False,
            sku=sku,
            payload={"variant": variant} if variant else None,
            quantity=max(int(quantity or 1), 1),
            sale_order_id=order.id or False,
        )
        if events and order:
            order._vela_remember_visit({"consent": True, "session": events.session,
                                        "visitor": events.visitor})
        return values


class VelaPaymentPortal(PaymentPortal):
    @route()
    def shop_payment_transaction(self, order_id, access_token, *args, **kwargs):
        try:
            return super().shop_payment_transaction(order_id, access_token, *args, **kwargs)
        except Exception as exc:
            _emit_failure(exc, order_id)
            raise
