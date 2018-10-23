import json

from datetime import datetime
from sqlalchemy import desc

from flask_babel import lazy_gettext as _

from .. import c3bottles, db

from .location import Location
from .report import Report
from .visit import Visit


class DropPoint(db.Model):
    """
    A location in the venue for visitors to drop their empty bottles.

    A drop point consists of a sign "bottle drop point <number>" at the
    wall which tells visitors that a drop point should be present there
    and a number of empty crates to drop bottles into.

    If the `removed` column is not null, the drop point has been removed
    from the venue (numbers are not reassigned).

    Each drop point is referenced by a unique number, which is
    consequently the primary key to identify a specific drop point. Since
    the location of drop points may change over time, it is not simply
    saved in the table of drop points but rather a class itself.
    """

    number = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=False)

    time = db.Column(db.DateTime)

    removed = db.Column(db.DateTime)

    locations = db.relationship(
        "Location",
        order_by="Location.time"
    )

    reports = db.relationship(
        "Report",
        lazy="dynamic"
    )

    visits = db.relationship(
        "Visit",
        lazy="dynamic"
    )

    type = db.Column(db.Text, default="drop_point")

    def __init__(
            self,
            number,
            description=None,
            lat=None,
            lng=None,
            level=None,
            time=None,
            type='bottle'
    ):
        """
        Create a new drop point object.

        New drop point objects will be added to the database automatically
        if the creation was successful. A location will also be added
        automatically.

        :raises ValueError: If an error occurred during creation of the drop
            point. The error message will contain a tuple of dicts which
            indicate in which part of the creation the error occurred.
        """

        errors = []

        try:
            self.number = int(number)
        except (TypeError, ValueError):
            errors.append({
                "number": _("Drop point number is not a number.")
            })
        else:
            if self.number < 1:
                errors.append({
                    "number": _("Drop point number is not positive.")
                })
            with db.session.no_autoflush:
                if db.session.query(DropPoint).get(self.number):
                    errors.append({
                        "number": _("That drop point already exists.")
                    })

        self.type = type

        if time and not isinstance(time, datetime):
            errors.append({
                "DropPoint": _("Creation time not a datetime object.")
            })

        if isinstance(time, datetime) and time > datetime.today():
            errors.append({
                "DropPoint": _("Creation time in the future.")
            })

        self.time = time if time else datetime.today()

        try:
            Location(
                self,
                time=self.time,
                description=description,
                lat=lat,
                lng=lng,
                level=level
            )
        except ValueError as e:
            errors += e.args

        if errors:
            raise ValueError(*errors)

        db.session.add(self)

    def remove(self, time=None):
        """
        Remove a drop point.

        This will not actually purge a drop point from the database but
        simply mark it as removed so it will no longer show up in the
        frontend. The time of removal can be given optionally and will
        default to :func:`datetime.today()`.
        """

        if self.removed:
            raise RuntimeError({
                "DropPoint": _("Drop point already removed.")
            })

        if time and not isinstance(time, datetime):
            raise TypeError({
                "DropPoint": _("Removal time not a datetime object.")
            })

        if time and time > datetime.today():
            raise ValueError({
                "DropPoint": _("Removal time in the future.")
            })

        self.removed = time if time else datetime.today()

    def report(self, state=None, time=None):
        """
        Submit a report for a drop point.
        """
        Report(self, time=time, state=state)

    def visit(self, action=None, time=None):
        """
        Perform a visit of a drop point.
        """
        Visit(self, time=time, action=action)

    def get_typename(self):
        if self.type == 'trashcan':
            return "Trashcan"
        return "Drop Point"

    def get_current_location(self):
        """
        Get the current location of a drop point, if it has been set.

        This will return `None`, if no location has been set yet.
        """
        return self.locations[-1] if self.locations else None

    def get_total_report_count(self):
        """
        Get the total number of reports of a drop point.
        """
        return self.reports.count()

    def get_new_report_count(self):
        """
        Get the number of reports since the last visit of a drop point.
        """
        last_visit = self.get_last_visit()
        if last_visit:
            return self.reports. \
                filter(Report.time > last_visit.time). \
                count()
        else:
            return self.get_total_report_count()

    def get_last_state(self):
        """
        Get the current state of a drop point.

        The state is influenced by two mechanisms:

        * Reports: a report will always set the drop point to the state
          that has been reported by the reporter, irrespective of the
          state before.
        * Visits: If a visit was performed since the last report, the
          drop point is now either empty or unchanged and therefore,
          if the drop point was emptied, the empty state is returned.
          If the drop point was not emptied during the visit, the last
          reported state will be returned.

        If neither reports nor visits have been recorded yet or only visits
        without any actions, the drop point state is returned as new.
        """
        last_report = self.get_last_report()
        last_visit = self.get_last_visit()

        if last_report is not None and last_visit is not None:
            if last_visit.time > last_report.time:
                visits = self.visits. \
                    filter(Visit.time > last_report.time). \
                    order_by(Visit.time.desc()). \
                    all()
                for visit in visits:
                    if visit.action == Visit.actions[0]:
                        return Report.states[-1]
                return last_report.state

        if last_report is not None:
            return last_report.state

        if last_visit is not None:
            if last_visit.action == Visit.actions[0]:
                return Report.states[-1]

        return Report.states[1]

    def get_last_report(self):
        """
        Get the last report of a drop point.
        """
        return self.reports.order_by(Report.time.desc()).first()

    def get_last_visit(self):
        """
        Get the last visit of a drop point.
        """
        return self.visits.order_by(Visit.time.desc()).first()

    def get_new_reports(self):
        """
        Get the reports since the last visit of a drop point.

        This method returns all reports for this drop point since the last
        visit ordered descending by time, i.e. the newest report is the first
        in the list. If no visits have been recorded yet, all reports are
        returned.
        """
        last_visit = self.get_last_visit()
        if last_visit:
            return self.reports. \
                filter(Report.time > last_visit.time). \
                order_by(Report.time.desc()). \
                all()
        else:
            return self.reports.order_by(Report.time.desc()).all()

    def get_history(self):
        history = []

        for visit in self.visits.all():
            history.append({
                "time": visit.time,
                "visit": visit
            })

        for report in self.reports.all():
            history.append({
                "time": report.time,
                "report": report
            })

        for location in self.locations:
            history.append({
                "time": location.time,
                "location": location
            })

        history.append({
            "time": self.time,
            "drop_point": self
        })

        if self.removed:
            history.append({
                "time": self.removed,
                "removed": True
            })

        return sorted(history, key=lambda k: k["time"], reverse=True)

    def get_visit_interval(self):
        """
        Get the visit interval for this drop point.

        This method returns the visit interval for this drop point
        in seconds.

        This is not implemented as a static method or a constant
        since in the future the visit interval might depend on
        the location of drop points, time of day or a combination
        of those.
        """

        return 60 * c3bottles.config.get("BASE_VISIT_INTERVAL", 120)

    def get_priority_factor(self):

        # The priority of a removed drop point obviously is always 0.
        if self.removed:
            return 0

        new_reports = self.get_new_reports()

        # This is the starting priority. The report weight should
        # be scaled relative to 1, so this can be interpreted as a
        # number of standing default reports ensuring that every
        # drop point's priority increases slowly if it is not
        # visited even if no real reports come in.
        priority = c3bottles.config.get("DEFAULT_VISIT_PRIORITY", 1)

        i = 0
        for report in new_reports:
            priority += report.get_weight() / 2**i
            i += 1

        priority /= (1.0 * self.get_visit_interval())

        return priority

    def get_priority_base_time(self):
        """
        Get the base time for visit priority calculation of a drop point.

        This is either the time of the last visit, or, if no visit has been
        performed yet, the creation time of the drop point.
        """
        if self.get_last_visit():
            return self.get_last_visit().time
        else:
            return self.time

    def get_priority(self):
        """
        Get the priority to visit this drop point.

        The priority to visit a drop point mainly depends on the
        number and weight of reports since the last visit.

        In addition, priority increases with time since the last
        visit even if the states of reports indicate a low priority.
        This ensures that every drop point is visited from time to
        time.
        """

        priority = self.get_priority_factor() * \
            (datetime.today() - self.get_priority_base_time()).total_seconds()

        return round(priority, 2)

    @staticmethod
    def get(number):
        try:
            return db.session.query(DropPoint).get(number)
        except TypeError:
            return None

    @classmethod
    def get_dp_info(cls, number):
        dp = cls.get(number)
        if dp is not None:
            return {
                "number": dp.number,
                "type": dp.type,
                "description": dp.get_current_location().description,
                "reports_total": dp.get_total_report_count(),
                "reports_new": dp.get_new_report_count(),
                "priority": dp.get_priority(),
                "priority_factor": dp.get_priority_factor(),
                "base_time": dp.get_priority_base_time().strftime("%s"),
                "last_state": dp.get_last_state(),
                "removed": True if dp.removed else False,
                "lat": dp.get_current_location().lat,
                "lng": dp.get_current_location().lng,
                "level": dp.get_current_location().level
            }
        else:
            return None

    @classmethod
    def get_dp_json(cls, number):
        """
        Get a JSON string characterizing a drop point.

        This returns a JSON representation of the dict constructed by
        :meth:`get_dp_info()`.
        """
        return json.dumps(
            {number: cls.get_dp_info(number)},
            indent=4 if c3bottles.debug else None
        )

    @staticmethod
    def get_dps_json(type='bottle', time=None):
        """
        Get drop points as a JSON string.

        If a time has been given as optional parameters, only drop points
        are returned that have changes since that time stamp, i.e. have
        been created, visited, reported or changed their location.
        """

        if time is None:
            dps = db.session.query(DropPoint).filter(DropPoint.type == type).all()
        else:
            dp_set = set()
            dp_set.update(
                [dp for dp in DropPoint.query.filter(DropPoint.time > time and DropPoint.type == type).all()],
                [l.dp for l in Location.query.filter(Location.time > time).all()],
                [v.dp for v in Visit.query.filter(Visit.time > time).all()],
                [r.dp for r in Report.query.filter(Report.time > time).all()]
            )
            dps = list(dp_set)

        ret = {}

        for dp in dps:
            ret[dp.number] = DropPoint.get_dp_info(dp.number)

        return json.dumps(ret, indent=4 if c3bottles.debug else None)

    @staticmethod
    def get_next_free_number():
        """
        Get the next free drop point number.
        """
        last = db.session.query(DropPoint) \
            .order_by(desc(DropPoint.number)) \
            .limit(1).first()
        if last:
            return last.number + 1
        else:
            return 1

    def __repr__(self):
        return "Drop point %s (%s)" % (
            self.number,
            "inactive" if self.removed else "active"
        )
