from flask import render_template, request, g, abort, make_response, url_for, flash, redirect
from flask_babel import lazy_gettext

from .. import c3bottles, db
from ..model.category import categories_sorted
from ..model.drop_point import DropPoint
from . import needs_editing


@c3bottles.route("/create", methods=("GET", "POST"))
@c3bottles.route(
    "/create/<level>/<float:lat>/<float:lng>",
    methods=("GET", "POST")
)
@needs_editing
def create_dp(lat=None, lng=None, level=None, description=None, errors=None):
    if request.method == "POST":
        number = int(request.form.get("number"))
        category_id = int(request.form.get("category_id"))
        description = request.form.get("description")
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
        level = int(request.form.get("level"))
        try:
            dp = DropPoint(
                number=number, category_id=category_id, description=description,
                lat=lat, lng=lng, level=level
            )
        except ValueError as e:
            errors = e.args
        else:
            db.session.commit()
            flash({
                "class": "success disappear",
                "text": lazy_gettext(
                    "Your %(category)s has been created successfully.", category=dp.category
                )
            })
            return redirect("{}#{}/{}/{}/3".format(url_for("dp_map"), level, lat, lng))
    else:
        number = DropPoint.get_next_free_number()

    if errors is not None:
        error_list = [v for d in errors for v in d.values()]
        error_fields = [k for d in errors for k in d.keys()]
    else:
        error_list = []
        error_fields = []

    return render_template(
        "create.html",
        number=number,
        lat=lat,
        lng=lng,
        level=int(level),
        description=description,
        error_list=error_list,
        error_fields=error_fields,
        categories=categories_sorted(),
    )


@c3bottles.route("/create.js/<level>/<float:lat>/<float:lng>")
def create_dp_js(level, lat, lng):
    resp = make_response(render_template(
        "js/create_dp.js",
        all_dps_json=DropPoint.get_dps_json(),
        level=int(level),
        lat=lat,
        lng=lng
    ))
    resp.mimetype = "application/javascript"
    return resp
