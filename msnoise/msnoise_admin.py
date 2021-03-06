from flask import Flask, redirect, request
from flask.ext.admin import Admin, BaseView, expose
import flask, time, json, socket

from flask.ext.admin.contrib.sqla import ModelView
from flask import flash
from wtforms.validators import ValidationError
from flask.ext.admin.actions import action
from flask.ext.admin.babel import ngettext, lazy_gettext

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE, CDN
from bokeh.templates import RESOURCES

from .api import *
from .msnoise_table_def import *


class GenericView(BaseView):
    name = "MSNoise"
    page = ""
    @expose('/')
    def index(self):
        return self.render('admin/%s.html'%self.page)

class FilterView(ModelView):
    view_title = "Filter Configuration"
    name = "filter"
    # Disable model creation
    def mwcs_low(form, field):
        if field.data <= form.data['low']:
            raise ValidationError("'mwcs_low' should be (at least slightly) greater than 'low'")
            
    def mwcs_high(form, field):
        if field.data <= form.data['mwcs_low']:
            raise ValidationError("'mwcs_high' should be greater than 'mwcs_low'")
    
    def high(form, field):
        if field.data <= form.data['mwcs_high']:
            raise ValidationError("'high' should be (at least slightly) greater than 'mwcs_high'")
    
    def mwcs_step(form, field):
        if field.data > form.data['mwcs_wlen']:
            raise ValidationError("'mwcs_step' should be smaller or equal to 'mwcs_wlen'")
    
    form_args = dict(
        mwcs_low=dict(validators=[mwcs_low]),
        mwcs_high=dict(validators=[mwcs_high]),
        high=dict(validators=[high]),
        mwcs_step=dict(validators=[mwcs_step]),
    )
    
    column_list = ('ref','low', 'mwcs_low', 'mwcs_high', 'high',
                   'rms_threshold', 'mwcs_wlen', 'mwcs_step', 'used')
    form_columns = ('low', 'mwcs_low', 'mwcs_high', 'high',
                   'rms_threshold', 'mwcs_wlen', 'mwcs_step', 'used')
    
    def __init__(self, session, **kwargs):
        # You can pass name and other parameters if you want to
        super(FilterView, self).__init__(Filter, session, **kwargs)
        
    @action('used',
            lazy_gettext('Toggle Used'),
            lazy_gettext('Are you sure you want to update selected models?'))
    def used(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            if s.used:
                s.used = False
            else:
                s.used = True
        self.session.commit()
        return  


class StationView(ModelView):
    view_title = "Station Configuration"
    column_filters = ('net', 'used')
    
    def __init__(self, session, **kwargs):
        super(StationView, self).__init__(Station, session, **kwargs)
    
    @action('used',
            lazy_gettext('Toggle Used'),
            lazy_gettext('Are you sure you want to update selected models?'))
    def used(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            if s.used:
                s.used = False
            else:
                s.used = True
        self.session.commit()
        return  


class DataAvailabilityView(ModelView):
    view_title = "Data Availability"
    can_create = False
    can_delete = False
    can_edit = True
    column_filters = ('net', 'sta', 'comp','data_duration','gaps_duration','samplerate','flag')
    def __init__(self, session, **kwargs):
        super(DataAvailabilityView, self).__init__(DataAvailability, session, **kwargs)
    
    @action('modified',
            lazy_gettext('Mark as (M)odified'),
            lazy_gettext('Are you sure you want to update selected models?'))
    def modified(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        count = 0
        for s in query.all():
            s.flag = 'M'
            count += 1
        self.session.commit()
        flash(ngettext('Model was successfully flagged (M)odified.',
               '%(count)s models were successfully flagged (M)odified.',
               count,
               count=count))
        return     
    

class JobView(ModelView):
    view_title = "Jobs"
    can_create = False
    can_delete = True
    can_edit = True
    column_filters = ('pair','jobtype','flag')
    
    def __init__(self, session, **kwargs):
        super(JobView, self).__init__(Job, session, **kwargs)
    
    @action('todo',
        lazy_gettext('Mark as (T)odo'),
        lazy_gettext('Are you sure you want to update selected models?'))
    def todo(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            s.flag = 'T'
        self.session.commit()
        return
    
    @action('done',
        lazy_gettext('Mark as (D)one'),
        lazy_gettext('Are you sure you want to update selected models?'))
    def done(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            s.flag = 'D'
        self.session.commit()
        return
    
    @action('deletetype',
        lazy_gettext('Delete all Jobs of the same "Type"'),
        lazy_gettext('Are you sure you want to delete all those models?'))
    def deletetype(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            type_to_delete = s.type
        self.get_query().filter(Job.jobtype == type_to_delete).delete()
        self.session.commit()
        return
    
    @action('massTodo',
        lazy_gettext('Mark all Jobs of the same Type as (T)odo'),
        lazy_gettext('Are you sure you want to update all those models?'))
    def massTodo(self, ids):
        model_pk = getattr(self.model, self._primary_key)
        query = self.get_query().filter(model_pk.in_(ids))
        for s in query.all():
            type_to_delete = s.type
        
        for s in self.get_query().filter(Job.jobtype == type_to_delete).all():
            s.flag = 'T'
        self.session.commit()
        return


class ConfigView(ModelView):
    # Disable model creation
    view_title = "MSNoise General Configuration"
    def no_root_allowed(form, field):
        if field.data == 'root':
            raise ValidationError('"root" is not allowed')
 
    # inline_models = (Config,)
    form_args = dict(
        value=dict(validators=[no_root_allowed])
    )
    can_create = False
    can_delete = False
    page_size = 50
    # Override displayed fields
    column_list = ('name', 'value')

    def __init__(self, session, **kwargs):
        # You can pass name and other parameters if you want to
        super(ConfigView, self).__init__(Config, session, **kwargs)

def getitem(obj, item, default):
    if item not in obj:
        return default
    else:
        return obj[item]


def select_filter():
    db = connect()
    filters = []
    query = get_filters(db, all=False)
    for f in query:
        filters.append({'optid':f.ref, 'text':"%.2f - %.2f"%(f.low, f.high)})
    db.close()
    return filters


def select_pair():
    db = connect()
    stations = ["%s.%s" % (s.net, s.sta) for s in get_stations(db,all=False)]
    pairs = itertools.combinations(stations, 2)
    output = []
    i = 0
    for pair in pairs:
        output.append({'optid':i, 'text':"%s - %s"%(pair[0],pair[1])})
        i+=1
    db.close()
    return output


class ResultPlotter(BaseView):
    name = "MSNoise"
    view_title = "Result Plotter"

    @expose('/')
    def index(self):
        args = flask.request.args

        filters = select_filter()
        pairs = select_pair()

        # Get all the form arguments in the url with defaults
        filter = int(getitem(args, 'filter', 1))
        pair = int(getitem(args, 'pair', 0))
        component = getitem(args, 'component', 'ZZ')
        format = getitem(args, 'format', 'stack')

        db = connect()
        station1, station2 = pairs[pair]['text'].replace('.','_').split(' - ')
        start, end, dates = build_ref_datelist(db)
        i, result = get_results(db,station1, station2, filter, component, dates, format=format)

        if format == 'stack':
            if i != 0:
                maxlag = float(get_config(db, 'maxlag'))
                x = np.linspace(-maxlag, maxlag, get_maxlag_samples(db))
                y = result
        db.close()

        fig = figure(title=pairs[pair]['text'], plot_width=1000)
        fig.line(x, y, line_width=2)

        plot_resources = RESOURCES.render(
            js_raw=CDN.js_raw,
            css_raw=CDN.css_raw,
            js_files=CDN.js_files,
            css_files=CDN.css_files,
        )

        script, div = components(fig, INLINE)
        return self.render(
            'admin/results.html',
            plot_script=script, plot_div=div, plot_resources=plot_resources,
            filter_list=filters,
            pair_list=pairs
        )


class InterferogramPlotter(BaseView):
    name = "MSNoise"
    view_title = "Interferogram Plotter"

    @expose('/')
    def index(self):
        return self.render('admin/interferogram.html')


class DataAvailabilityPlot(BaseView):
    name = "MSNoise"
    view_title = "Data Availability"

    @expose('/')
    def index(self):
        return self.render('admin/data_availability.html')


class BugReport(BaseView):
    name = "MSNoise"
    view_title = "BugReport"

    @expose('/')
    def index(self):
        return self.render('admin/bugreport.html')

app = Flask(__name__, template_folder='templates')
app.secret_key = 'why would I tell you my secret key?'


@app.route('/admin/networks.json')
def networksJSON():
    db = connect()
    data = {}
    networks = get_networks(db)
    for network in networks:
        stations = get_stations(db, net=network)
        data[network] = [s.sta for s in stations]
    o = json.dumps(data)
    db.close()
    return flask.Response(o, mimetype='application/json')

@app.route('/admin/filters.json')
def filtersJSON():
    db = connect()
    data = {}
    filters = get_filters(db, all=False)
    for f in filters:
        data[f.ref] = "%.2f - %.2f"%(f.low, f.high)
    db.close()
    o = json.dumps(data)
    db.close()
    return flask.Response(o, mimetype='application/json')

@app.route('/admin/components.json')
def componentsJSON():
    db = connect()
    components = get_components_to_compute(db)
    data = {}
    for i,c in enumerate(components):
        data[i] = c
    db.close()
    o = json.dumps(data)
    db.close()
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/pairs.json')
def pairs():
    db = connect()
    stations = ["%s.%s" % (s.net, s.sta) for s in get_stations(db,all=False)]
    pairs = itertools.combinations(stations, 2)
    output = []
    for pair in pairs:
        output.append("%s - %s"%(pair[0],pair[1]))
    o = json.dumps(output)
    db.close()
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/bugreport.json')
def bugreporter():
    from bugreport import main
    output = main(modules=True, show=False)

    o = json.dumps(output)
    db.close()
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/data_availability.json',methods=['GET','POST'])
def dataAvail():
    data = flask.request.get_json()
    db = connect()
    data = get_data_availability(db, net=data['net'], sta=data['sta'],comp='HHZ')
    o = {'dates':[o.starttime.strftime('%Y-%m-%d') for o in data]}
    db.close()
    o['result']='ok'
    o = json.dumps(o)
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/all_results.json',methods=['POST'])
def allresults():
    data = flask.request.get_json(force=True)
    db = connect()
    station1, station2 = data['pair'].replace('.','_').split(' - ')
    filterid = int(data['filter'])
    components = data['component']
    format = data['format']
    start, end, dates = build_ref_datelist(db)
    i, result = get_results(db,station1, station2, filterid, components, dates, format=format)
    
    data = {}
    if format == 'stack':
        if i != 0:
            maxlag = float(get_config(db, 'maxlag'))
            data['x'] = np.linspace(-maxlag, maxlag, get_maxlag_samples(db)).tolist()
            data['y'] = result.tolist()
            data["info"] = "Data OK"
        else:
            data["info"] = "No Data"
    else:
        if i != 0:
            x = []
            for y in range(len(dates)):
                r = result[y]
                r = np.nan_to_num(r)
                x.append( r.tolist() )
            data["image"] = x
            data["nx"] = len(r)
            data["ny"] = len(x)
            data["info"] = "Data OK"
        else:
            data["info"] = "No Data"
    o = json.dumps(data)
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/new_jobs_TRIG.json')
def new_jobsTRIG():
    from s02new_jobs import main
    count = main()
    global db
    db.flush()
    db.commit()

    o = {}
    o['count']=count
    o = json.dumps(o)
    return flask.Response(o, mimetype='application/json')
    

@app.route('/admin/jobs_list.json')
def joblists():
    jobtype = flask.request.args['type']
    db = connect()
    data = get_job_types(db,jobtype)
    db.close()
    o = {'T':0,'I':0,'D':0}
    for count, flag in data:
        o[flag] = count

    o = json.dumps(o)
    return flask.Response(o, mimetype='application/json')


@app.route('/admin/data_availability_flags.json')
def DA_flags():
    db = connect()
    data = count_data_availability_flags(db)
    db.close()
    o = {'N':0,'M':0,'A':0}
    for count, flag in data:
        o[flag] = count
    o = json.dumps(o)
    return flask.Response(o, mimetype='application/json')


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@app.route('/shutdown', methods=['GET'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


# Flask views
@app.route('/')
def index():
    return redirect("/admin/", code=302)


def main(port=5000):
    global db
    db = connect()
    plugins = get_config(db, "plugins")
    db.close()

    db = connect()

    admin = Admin(app)
    admin.name = "MSNoise"
    admin.add_view(StationView(db,endpoint='stations', category='Configuration'))
    admin.add_view(FilterView(db,endpoint='filters', category='Configuration'))
    admin.add_view(ConfigView(db,endpoint='config', category='Configuration'))

    admin.add_view(DataAvailabilityView(db,endpoint='data_availability',category='Database'))

    admin.add_view(JobView(db,endpoint='jobs',category='Database'))


    admin.add_view(DataAvailabilityPlot(endpoint='data_availability_plot',category='Results'))
    admin.add_view(ResultPlotter(endpoint='results',category='Results'))
    admin.add_view(InterferogramPlotter(endpoint='interferogram',category='Results'))

    if plugins:
        plugins = plugins.split(',')
        for ep in pkg_resources.iter_entry_points(group='msnoise.plugins.admin_view'):
            module_name = ep.module_name.split(".")[0]
            if module_name in plugins:
                admin.add_view(ep.load()(db))

    a = GenericView(endpoint='about',category='Help', name='About')
    a.page = "about"
    admin.add_view(a)
    admin.add_view(BugReport(name='Bug Report', endpoint='bugreport', category='Help'))


    app.run(host='0.0.0.0', debug=True, port=port)
