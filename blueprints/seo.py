from flask import Blueprint
from utils import *
from .limiter import limiter

seo = Blueprint("seo", __name__)


@seo.route("/sitemap.xml")
@limiter.exempt
def serve_sitemap():
    return send_file("misc/sitemap.xml")


@seo.route("/security.txt")
@limiter.exempt
def serve_security():
    return send_file("misc/security.txt")


@seo.route("/humans.txt")
@limiter.exempt
def serve_humans():
    return send_file("misc/humans.txt")


@seo.route("/robots.txt")
@limiter.exempt
def serve_robots():
    return send_file("misc/robots.txt")
