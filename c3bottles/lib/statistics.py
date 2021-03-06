from c3bottles.model.drop_point import DropPoint
from c3bottles.model.report import Report
from c3bottles.model.visit import Visit


class Statistics(object):

    @property
    def drop_point_count(self):
        try:
            return DropPoint.query.filter(DropPoint.removed == None).count()  # noqa
        except:  # noqa
            return 0

    @property
    def report_count(self):
        try:
            return Report.query.count()
        except:  # noqa
            return 0

    @property
    def visit_count(self):
        try:
            return Visit.query.count()
        except:  # noqa
            return 0

    @property
    def drop_points_by_state(self):
        ret = {}
        for state in Report.states:
            ret[state] = 0
        try:
            for dp in DropPoint.query.all():
                if not dp.removed:
                    s = dp.last_state
                    ret[s] = ret[s] + 1 if s in ret else 1
        except:  # noqa
            pass
        return ret

    @property
    def reports_by_state(self):
        ret = {}
        for state in Report.states:
            try:
                ret[state] = Report.query.filter(Report.state == state).count()
            except:  # noqa
                ret[state] = 0
        return ret

    @property
    def visits_by_action(self):
        ret = {}
        for action in Visit.actions:
            try:
                ret[action] = Visit.query.filter(Visit.action == action).count()
            except:  # noqa
                ret[action] = 0
        return ret


stats_obj = Statistics()
