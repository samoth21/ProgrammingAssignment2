import os
import os.path as op
from flask import Flask, url_for, redirect, render_template, request, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user
from flask_security.utils import encrypt_password
import flask_admin
from flask_admin.contrib import sqla
from flask_admin import helpers as admin_helpers
from flask_admin import Admin, form
from sqlalchemy.event import listens_for
from flask_admin.form import rules
from flask import has_app_context
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.contrib.sqla import ModelView
from flask_admin.form.rules import Field
from wtforms.fields import StringField
from flask_admin.contrib.sqla.filters import BaseSQLAFilter
from sqlalchemy.orm import deferred
import warnings
#from flask.ext.admin.contrib.sqla.view import func
#from flask_babelex import Babel

# Create Flask application
app = Flask(__name__)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)

'''
# Initialize babel
babel = Babel(app)

@babel.localeselector
def get_locale():
    override = request.args.get('lang')

    if override:
        session['lang'] = override

    return session.get('lang', 'en')
'''

# Create directory for file fields to use
file_path = op.join(op.dirname(__file__), 'static')
#file_path = "C:\\Users\\user\\Desktop"
try:
    os.mkdir(file_path)
except OSError:
    pass

# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)

# Define the reviewers when apply release
project_users = db.Table(
    'project_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('project_id', db.Integer(), db.ForeignKey('project.id'))
)

# Define the team when apply release
project_teams = db.Table(
    'project_teams',
    db.Column('team_id', db.Integer(), db.ForeignKey('team.id')),
    db.Column('project_id', db.Integer(), db.ForeignKey('project.id'))
)


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name

class Team(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    
    #reviewer_1 = db.relationship('Project', backref='reviewer_1')
    reviewer_2 = db.relationship('Project', backref='reviewer_2')
    

    def __str__(self):
        return self.first_name


class Project(db.Model):
  
    id = db.Column(db.Integer, primary_key=True)
    team = db.Column(db.Unicode(64))
    name = db.Column(db.Unicode(128))  
    project_name = db.Column(db.Unicode(128))
    version = db.Column(db.Unicode(128))
    SVN = db.Column(db.UnicodeText)
    #submitted_at = db.Column(db.DateTime())
    notes = db.Column(db.UnicodeText)
    reviewer1 = db.Column(db.Unicode(128)) 
    reviewer1_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    #reviewer2_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    review1 = db.Column(db.Boolean())
    comment1 = db.Column(db.UnicodeText)
    reviewer2 = db.Column(db.Unicode(128))  
    review2 = db.Column(db.Boolean())
    comment2 = db.Column(db.UnicodeText)
    approve = db.Column(db.Boolean())
    comment3 = db.Column(db.UnicodeText)  
    reviewers = db.relationship('User', secondary=project_users,
                            backref=db.backref('projects', lazy='dynamic'))
    teams = db.relationship('Team', secondary=project_teams,
                            backref=db.backref('projectss', lazy='dynamic')) 
    #reviewers2 = db.relationship('User', secondary=project_users,
                            #backref=db.backref('projects', lazy='dynamic'))
    def __unicode__(self):
        return self.name


# Customized the filter interface
class CustomView(ModelView):
    list_template = 'list.html'
    create_template = 'create.html'
    edit_template = 'edit.html'

# In order to make "readonly" field
class CustomizableField(Field):
    def __init__(self, field_name, render_field='lib.render_field', field_args={}):
        super(CustomizableField, self).__init__(field_name, render_field)
        self.extra_field_args = field_args

    def __call__(self, form, form_opts=None, field_args={}):
        field_args.update(self.extra_field_args)
        return super(CustomizableField, self).__call__(form, form_opts, field_args)

# Dynamically make "readonly" field afer aproval
class ReadOnlyStringField(StringField):
    @staticmethod
    def readonly_condition():
        # Dummy readonly condition
        return False

    def __call__(self, *args, **kwargs):
        # Adding `readonly` property to `input` field
        if self.readonly_condition():
            kwargs.setdefault('readonly', True)
        return super(ReadOnlyStringField, self).__call__(*args, **kwargs)

    def populate_obj(self, obj, name):
        # Preventing application from updating field value
        # (user can modify web page and update the field)
        if not self.readonly_condition():
            super(ReadOnlyStringField, self).populate_obj(obj, name)

# Approve custom filter class
class FilterApprove(BaseSQLAFilter):
    def apply(self, query, value, alias=None):
        if value == '1':
            return query.filter(self.column == 1)
        else:
            return query.filter(self.column != 1)

    def operation(self):
        return 'Status'
'''
#class File(db.Model):
class File(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(64))
    path = db.Column(db.Unicode(128))

    def __unicode__(self):
        return self.name

# Delete hooks for models, delete files if models are getting deleted
@listens_for(File, 'after_delete')
def del_file(mapper, connection, target):
    if target.path:
        try:
            os.remove(op.join(file_path, target.path))
        except OSError:
            # Don't care if was not deleted because it does not exist
            pass
'''

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


# Create customized model view class
class MyModelView(sqla.ModelView):

    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False

        #if current_user.has_role('superuser'):
        if current_user.has_role('administrator'):
            return True

        return False

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for('security.login', next=request.url))

class UserView(MyModelView):
    column_list = ['first_name', 'last_name','email', 'password', 'active']
    form_create_rules = [
        #rules.Field('roles'),
        rules.Field('first_name'),
        rules.Field('last_name'),
        rules.Field('email'),
        rules.Field('password'),
        rules.Field('active')
      ]

    form_edit_rules = form_create_rules
    create_template = 'rule_create.html'
    edit_template = 'rule_edit.html'

class TeamView(MyModelView):
    column_list = ['name','description']
    form_create_rules = [
        rules.Field('name'),
        rules.Field('description')
      ]

    form_edit_rules = form_create_rules
    create_template = 'rule_create.html'
    edit_template = 'rule_edit.html'

  
class SWProjectView(sqla.ModelView):
    column_labels = dict(teams='Team', reviewers='Reviewer 1',SVN='SVN',version='Ver')
                         
    #column_labels = dict(reviewers='Reviewer 1')
    #column_labels = dict(project_name='Project')
    #column_labels = dict(SVN='SVN')
    column_list = ['teams','name', 'project_name','version','SVN', 'notes',
                   'reviewers','comment1','review1','reviewer_2','comment2','review2',
                   'comment3','approve' ]
    
    # All fields become Readonly if approved
    form_overrides = {
        'project_name': ReadOnlyStringField,
        #'team': ReadOnlyStringField,
        'name': ReadOnlyStringField,
        'version': ReadOnlyStringField,
        'SVN': ReadOnlyStringField,
        'notes': ReadOnlyStringField,
        'comment1': ReadOnlyStringField,
        'comment2': ReadOnlyStringField,
        #'comment3': ReadOnlyStringField,
        #'reviewer1': ReadOnlyStringField,
        #'reviewer2': ReadOnlyStringField,
        #'reviewer_1': ReadOnlyStringField,
    }

    def edit_form(self, obj=None):
        def readonly_condition():
            if obj is None:
                return False
            return obj.approve
        form = super(SWProjectView, self).edit_form(obj)
        form.project_name.readonly_condition = readonly_condition
        #form.team.readonly_condition = readonly_condition
        form.name.readonly_condition = readonly_condition
        form.version.readonly_condition = readonly_condition
        form.SVN.readonly_condition = readonly_condition
        form.notes.readonly_condition = readonly_condition
        form.comment1.readonly_condition = readonly_condition
        form.comment2.readonly_condition = readonly_condition
        #form.comment3.readonly_condition = readonly_condition
        #form.reviewer1.readonly_condition = readonly_condition
        #form.reviewer2.readonly_condition = readonly_condition
        #form.reviewer_1.readonly_condition = readonly_condition
        return form
    
    # The filters
    column_searchable_list = ('name', 'project_name',) 
    column_filters = [
        #FilterEqual(column=User.last_name, name='Last Name'),
        FilterApprove(column=Project.approve, name='Approve Status',
                            options=(('1', 'Approved'), ('2', 'Not Approved')))
    ]
    can_export = True
    '''
    form_widget_args = {
            'project_name': {
            'readonly': True
         },
        }
    '''
    
    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False
        #else:
            #return True      

        if current_user.has_role('user'):
            self.can_edit = True
            self.can_create = True
            self.can_delete = False
            return True
        if current_user.has_role('reviewer1'):
            self.can_edit = True
            self.can_create = True
            self.can_delete = False
            return True       
        if current_user.has_role('administrator') or current_user.has_role('reviewer2') or current_user.has_role('superuser'):
            self.can_edit = True
            self.can_create = True
            self.can_delete = True
            return True
        
        return False

    @property
    def _form_edit_rules(self):
        return rules.RuleSet(self, self.edit_form_rules)

    @_form_edit_rules.setter
    def _form_edit_rules(self, value):
   
        pass

    @property
    def _form_create_rules(self):
        return rules.RuleSet(self, self.create_form_rules)

    @_form_create_rules.setter
    def _form_create_rules(self, value):
        pass

    @property
    def edit_form_rules(self):
       
        if not has_app_context() or current_user.has_role('reviewer1'):
         edit_form_rules = [        
            rules.Header('Personal Info'),
            #rules.Field('team'),
            #rules.Field('teams'),
            rules.Field('name'),
            rules.Header('Project Info'),
            rules.Field('project_name'),
            rules.Field('version'),
            rules.Field('SVN'),
            #rules.Field('submitted_at'),
            rules.Field('notes'),
            rules.Header('Reviewers'),
            #rules.Field('reviewer1'),
            rules.Field('comment1'),
            #CustomizableField('reviewer2', field_args={
            #     'readonly': True
            #}),
            CustomizableField('comment2', field_args={
                 'readonly': True
            }),
            CustomizableField('review1', field_args={
                 'readonly': True
            }),
            #rules.Field('reviewers'),
          ]
         
        if not has_app_context() or current_user.has_role('reviewer2'):
         edit_form_rules = [        
            rules.Header('Personal Info'),
            #rules.Field('team'),
            #rules.Field('teams'),
            rules.Field('name'),
            rules.Header('Project Info'),
            rules.Field('project_name'),
            rules.Field('version'),
            rules.Field('SVN'),
            #rules.Field('submitted_at'),
            CustomizableField('notes', field_args={
                 'readonly': True
            }),
            rules.Header('Reviewers'),
            #rules.Field('reviewer1'),
            CustomizableField('comment1', field_args={
                 'readonly': True
            }),
            #rules.Field('reviewer2'),
            rules.Field('comment2'),
            CustomizableField('review2', field_args={
                 'readonly': True
            }),
            #rules.Field('reviewers'),
         ]
 
        if not has_app_context() or current_user.has_role('user'):
         edit_form_rules = [        
            rules.Header('Personal Info'),
            #CustomizableField('team', field_args={
             #    'readonly': True
            #}),
            #rules.Field('teams'),
            CustomizableField('name', field_args={
                 'readonly': True
            }),
            rules.Header('Project Info'),
            rules.Field('project_name'),
            rules.Field('version'),
            rules.Field('SVN'),
            #rules.Field('submitted_at'),
            rules.Field('notes'),
            rules.Header('Reviewers'),
            #rules.Field('reviewer1'),
            #CustomizableField('reviewer1', field_args={
             #    'readonly': not self.model.approve
            #}),           
            CustomizableField('comment1', field_args={
                 'readonly': True
            }),
            #rules.Field('reviewer2'),
            CustomizableField('comment2', field_args={
                 'readonly': True
            }),
            #rules.Field('reviewers'),
            #CustomizableField('review2', field_args={
             #    'readonly': True
            #}),
         ]
       
        if not has_app_context() or current_user.has_role('superuser') or current_user.has_role('administrator'):
         edit_form_rules = [        
            rules.Header('Personal Info'),
            #rules.Field('team'),
            rules.Field('teams'),
            rules.Field('name'),
            rules.Header('Project Info'),
            rules.Field('project_name'),
            rules.Field('version'),
            rules.Field('SVN'),
            #rules.Field('submitted_at'),
            rules.Field('notes'),
            rules.Header('Reviewers'),
            #rules.Field('reviewer1'),
            rules.Field('comment1'),
            rules.Field('review1'),
            #rules.Field('reviewer2'),
            rules.Field('comment2'),
            rules.Field('review2'),
            rules.Field('comment3'),
            rules.Field('approve'), 
            #CustomizableField('reviewer_1', field_args={
            #     'readonly': True
            #}),
            #rules.Field('reviewers'),
         ]
 
         '''
         if not has_app_context() or current_user.has_role('superuser'):
             edit_form_rules.append('approve')
         
         if not has_app_context() or current_user.has_role('reviewer1'):
             edit_form_rules.append('review1')
         if not has_app_context() or current_user.has_role('reviewer2'):
             edit_form_rules.append('review2')
         '''
        return edit_form_rules

    @property
    def create_form_rules(self):

        create_form_rules = [
            rules.Header('Personal Info'),
            rules.Field('teams'),
            #rules.Field('team'),
            rules.Field('name'),
            rules.Header('Project Info'),
            rules.Field('project_name'),
            rules.Field('version'),
            rules.Field('SVN'),
            rules.Field('notes'),
            rules.Header('Reviewers'),
            #rules.Field('reviewer1'),
            #rules.Field('reviewer2'),
            #rules.Field('reviewer_1'),
            rules.Field('reviewers'),
            rules.Field('reviewer_2'),
        ]
        return create_form_rules
        '''
        if not has_app_context() or current_user.has_role('superuser'):
            create_form_rules.append('approve')
        if not has_app_context() or current_user.has_role('reviewer1'):
            create_form_rules.append('review1')
        if not has_app_context() or current_user.has_role('reviewer2'):
            create_form_rules.append('review2')
        '''

#Inherit FileAdmin
class FileView(FileAdmin):
    #can_delete = False

    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False
           
        if current_user.has_role('administrator'):
            self.can_rename = True
            self.can_mkdir = True
            self.can_delete = True
            return True
        if current_user.has_role('superuser') or current_user.has_role('reviewer2'):
            self.can_rename = True
            self.can_mkdir = True
            self.can_delete = False
            return True
        if current_user.has_role('user') or current_user.has_role('reviewer1') :
            self.can_rename = False
            self.can_mkdir = False
            self.can_delete = False
            return True
        return False

# Flask views
@app.route('/')
def index():
    return render_template('index.html')

'''
# Flask views
@app.route('/')
def index():
    tmp = u"""
<p><a href="/admin/?lang=en">Click me to get to Admin! (English)</a></p>
<p><a href="/admin/?lang=cs">Click me to get to Admin! (Czech)</a></p>
<p><a href="/admin/?lang=de">Click me to get to Admin! (German)</a></p>
<p><a href="/admin/?lang=es">Click me to get to Admin! (Spanish)</a></p>
<p><a href="/admin/?lang=fa">Click me to get to Admin! (Farsi)</a></p>
<p><a href="/admin/?lang=fr">Click me to get to Admin! (French)</a></p>
<p><a href="/admin/?lang=pt">Click me to get to Admin! (Portuguese)</a></p>
<p><a href="/admin/?lang=ru">Click me to get to Admin! (Russian)</a></p>
<p><a href="/admin/?lang=pa">Click me to get to Admin! (Punjabi)</a></p>
<p><a href="/admin/?lang=zh_CN">Click me to get to Admin! (Chinese - Simplified)</a></p>
<p><a href="/admin/?lang=zh_TW">Click me to get to Admin! (Chinese - Traditional)</a></p>
"""
    return tmp
'''



# Create admin
admin = flask_admin.Admin(
    app,
    'Release Control System',
    # log in success page
    base_template='my_master.html',   
    template_mode='bootstrap3',
)

# Add model views and avoid warnings
#with warnings.catch_warnings():
#warnings.filterwarnings('ignore', 'Fields missing from ruleset', UserWarning)
admin.add_view(MyModelView(Role, db.session))
admin.add_view(UserView(User, db.session))
admin.add_view(TeamView(Team, db.session))
admin.add_view(SWProjectView(Project, db.session, name = "Project"))
#admin.add_view(SWProjectView(Project, db.session))
admin.add_view(FileView(file_path, '/static/', name='File'))
#admin.add_view(FileView(file_path, name='File'))

# define a context processor for merging flask-admin's template context into the
# flask-security views.
@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
        get_url=url_for
    )


def build_sample_db():
    """
    Populate a small db with some example entries.
    """

    import string
    import random

    db.drop_all()
    db.create_all()

    with app.app_context():
        user_role = Role(name='user')
        super_user_role = Role(name='superuser')
        db.session.add(user_role)
        db.session.add(super_user_role)
        db.session.commit()

        test_user = user_datastore.create_user(
            first_name='Admin',
            email='admin',
            password=encrypt_password('admin'),
            roles=[user_role, super_user_role]
        )

        first_names = [
            'Harry', 'Amelia', 'Oliver', 'Jack', 'Isabella', 'Charlie', 'Sophie', 'Mia',
            'Jacob', 'Thomas', 'Emily', 'Lily', 'Ava', 'Isla', 'Alfie', 'Olivia', 'Jessica',
            'Riley', 'William', 'James', 'Geoffrey', 'Lisa', 'Benjamin', 'Stacey', 'Lucy'
        ]
        last_names = [
            'Brown', 'Smith', 'Patel', 'Jones', 'Williams', 'Johnson', 'Taylor', 'Thomas',
            'Roberts', 'Khan', 'Lewis', 'Jackson', 'Clarke', 'James', 'Phillips', 'Wilson',
            'Ali', 'Mason', 'Mitchell', 'Rose', 'Davis', 'Davies', 'Rodriguez', 'Cox', 'Alexander'
        ]

        for i in range(len(first_names)):
            tmp_email = first_names[i].lower() + "." + last_names[i].lower() + "@example.com"
            tmp_pass = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(10))
            user_datastore.create_user(
                first_name=first_names[i],
                last_name=last_names[i],
                email=tmp_email,
                password=encrypt_password(tmp_pass),
                roles=[user_role, ]
            )
        db.session.commit()
    return

if __name__ == '__main__':

    # Build a sample db on the fly, if one does not exist yet.
    app_dir = os.path.realpath(os.path.dirname(__file__))
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db()

    # Start app
    #app.run(debug=True)
    app.run(port=5003)