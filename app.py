import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    print("WARNING: SECRET_KEY is not set. Using a default value.")
    SECRET_KEY = 'a_default_unsafe_secret_key'
app.secret_key = SECRET_KEY

basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

user_achievements = db.Table('user_achievements',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('achievement_id', db.Integer, db.ForeignKey('achievement.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    monthly_limit = db.Column(db.Float, default=0)
    saving_goal = db.Column(db.Float, nullable=True)
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")
    achievements = db.relationship('Achievement', secondary=user_achievements, lazy='subquery', backref=db.backref('users', lazy=True))
    recurring_expenses = db.relationship('RecurringExpense', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    category = db.Column(db.String(150))
    date = db.Column(db.Date)
    description = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=False, default='fa-star')

class RecurringExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    frequency = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    last_processed_date = db.Column(db.Date, nullable=True)

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4)])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, message='Password must be at least 8 characters long.')])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password', message='Passwords must match.')])
    submit = SubmitField('Change Password')

class ExpenseForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('Food', 'Food'),
        ('Transport', 'Transport'),
        ('Housing', 'Housing'),
        ('Subscriptions', 'Subscriptions'),
        ('Entertainment', 'Entertainment'),
        ('Other', 'Other')
    ])
    date = StringField('Date (YYYY-MM-DD)', validators=[DataRequired()])
    description = StringField('Description')
    submit = SubmitField('Add Expense')

class BudgetForm(FlaskForm):
    limit = DecimalField('Monthly Budget ($)', validators=[DataRequired()])
    submit = SubmitField('Save')

class GoalForm(FlaskForm):
    goal = DecimalField('Savings Goal ($)', validators=[DataRequired()])
    submit = SubmitField('Save Goal')

class RecurringExpenseForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('Food', 'Food'),
        ('Transport', 'Transport'),
        ('Housing', 'Housing'),
        ('Subscriptions', 'Subscriptions'),
        ('Entertainment', 'Entertainment'),
        ('Other', 'Other')
    ])
    description = StringField('Description', validators=[DataRequired()])
    frequency = SelectField('Frequency', choices=[
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('yearly', 'Yearly')
    ], validators=[DataRequired()])
    start_date = StringField('Start Date (YYYY-MM-DD)', validators=[DataRequired()])
    submit = SubmitField('Save Recurring Expense')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def award_achievement(user, achievement_name):
    achievement = Achievement.query.filter_by(name=achievement_name).first()
    if achievement and achievement not in user.achievements:
        user.achievements.append(achievement); flash(f" New Achievement!!|{achievement.name}|{achievement.description}|{achievement.icon}|gold", 'achievement'); db.session.commit()

def process_recurring_expenses(user):
    today = date.today(); recurring_expenses_list = RecurringExpense.query.filter_by(user_id=user.id).all()
    for rec_expense in recurring_expenses_list:
        if rec_expense.start_date > today: continue
        last_date = rec_expense.last_processed_date or rec_expense.start_date
        while True:
            next_due_date = None
            if rec_expense.frequency == 'monthly': next_due_date = last_date + relativedelta(months=1)
            elif rec_expense.frequency == 'weekly': next_due_date = last_date + relativedelta(weeks=1)
            elif rec_expense.frequency == 'yearly': next_due_date = last_date + relativedelta(years=1)
            if not next_due_date or next_due_date > today: break
            new_expense = Expense(user_id=user.id, amount=rec_expense.amount, category=rec_expense.category, description=f"(Recurringy) {rec_expense.description}", date=next_due_date)
            db.session.add(new_expense); rec_expense.last_processed_date = next_due_date; last_date = next_due_date
            flash(f'Recurring expense added automaticallyy: {rec_expense.description}', 'info')
    db.session.commit()

def setup_initial_data():
    """Populates the database with initial achievements if they don't exist."""
    achievements = {
        'First Step': ('Added your first expense. Great job!', 'fa-shoe-prints'),
        'Data Collector': ('Added 10 expenses.', 'fa-layer-group'),
        'Budget Master': ('Set your first monthly budget!', 'fa-piggy-bank'),
        'Goal Achiever': ('Congratulations! You reached your savings goal.', 'fa-bullseye'),
        'Automator': ('Set up your first recurring expense!', 'fa-robot')
    }
    for name, (desc, icon) in achievements.items():
        if not Achievement.query.filter_by(name=name).first():
            db.session.add(Achievement(name=name, description=desc, icon=icon))
    db.session.commit()

@app.route('/')
def home():
    return render_template('home.html', title='Welcome')

@app.route('/wallet')
@login_required
def wallet():
    process_recurring_expenses(current_user)
    selected_month = request.args.get('month', type=int)
    selected_category = request.args.get('category', type=str)
    current_year = datetime.now().year
    base_query = Expense.query.filter_by(user_id=current_user.id)
    query_for_views = base_query
    if selected_month:
        query_for_views = query_for_views.filter(db.extract('year', Expense.date) == current_year, db.extract('month', Expense.date) == selected_month)
    if selected_category:
        query_for_views = query_for_views.filter_by(category=selected_category)
    expenses_for_table = query_for_views.order_by(Expense.date.desc()).all()
    category_summary = query_for_views.with_entities(Expense.category, db.func.sum(Expense.amount).label('total')).group_by(Expense.category).order_by(db.func.sum(Expense.amount).desc()).all()
    labels = [item.category for item in category_summary]
    values = [float(item.total) for item in category_summary]
    budget_limit = current_user.monthly_limit or 0
    saving_goal = current_user.saving_goal or 0
    current_month_expenses = db.session.query(db.func.sum(Expense.amount)).filter(Expense.user_id == current_user.id, db.extract('year', Expense.date) == current_year, db.extract('month', Expense.date) == datetime.now().month).scalar() or 0
    budget_remaining = budget_limit - float(current_month_expenses)
    budget_used_percent = int((float(current_month_expenses) / budget_limit) * 100) if budget_limit > 0 else 0
    saving_progress = max(0, saving_goal - float(current_month_expenses)) if saving_goal else 0
    from calendar import month_name
    monthly_labels = [month_name[i] for i in range(1, 13)]
    yearly_summary = db.session.query(db.extract('month', Expense.date).label('month'), db.func.sum(Expense.amount).label('total')).filter(Expense.user_id == current_user.id, db.extract('year', Expense.date) == current_year).group_by(db.extract('month', Expense.date)).all()
    monthly_values_dict = {item.month: float(item.total) for item in yearly_summary}
    monthly_values = [monthly_values_dict.get(m, 0) for m in range(1, 13)]
    return render_template('dashboard.html', expenses=expenses_for_table, labels=labels, values=values, budget_limit=budget_limit, current_month_expenses=float(current_month_expenses), budget_remaining=budget_remaining, budget_used_percent=budget_used_percent, selected_month=selected_month, selected_category=selected_category, saving_goal=saving_goal, saving_progress=saving_progress, current_year=current_year, monthly_labels=monthly_labels, monthly_values=monthly_values)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists!', 'warning')
            return redirect(url_for('register'))
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    password_form = ChangePasswordForm()
    if password_form.validate_on_submit():
        if current_user.check_password(password_form.old_password.data):
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Incorrect old password.', 'danger')
    return render_template('profile.html', title='User Profile', password_form=password_form, achievements=current_user.achievements)

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('Your account and all associated data have been permanently deleted.', 'success')
    return redirect(url_for('login'))

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    form = ExpenseForm()
    if form.validate_on_submit():
        expense_date = datetime.strptime(str(form.date.data), '%Y-%m-%d').date()
        new_expense = Expense(amount=form.amount.data, category=form.category.data, date=expense_date, description=form.description.data, user_id=current_user.id)
        db.session.add(new_expense)
        db.session.commit()
        if len(current_user.expenses) == 1:
            award_achievement(current_user, 'First Step')
        elif len(current_user.expenses) == 10:
            award_achievement(current_user, 'Data Collector')
        if current_user.saving_goal and current_user.saving_goal > 0:
            total_spent = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=current_user.id).scalar()
            if total_spent and total_spent >= current_user.saving_goal:
                award_achievement(current_user, 'Goal Achiever')
        flash('Expense added successfully!', 'success')
        return redirect(url_for('wallet'))
    return render_template('add_expense.html', title='Add Expense', form=form)

@app.route('/edit_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        flash("You do not have permission to edit this expense.", "danger")
        return redirect(url_for('wallet'))
    form = ExpenseForm(obj=expense)
    if form.validate_on_submit():
        expense.amount = form.amount.data
        expense.category = form.category.data
        expense.date = datetime.strptime(str(form.date.data), '%Y-%m-%d').date()
        expense.description = form.description.data
        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('wallet'))
    form.date.data = expense.date.strftime('%Y-%m-%d')
    return render_template('edit_expense.html', title='Edit Expense', form=form)

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        flash("You do not have permission to delete this expense.", "danger")
        return redirect(url_for('wallet'))
    db.session.delete(expense)
    db.session.commit()
    flash("Expense has been deleted.", 'info')
    return redirect(url_for('wallet'))

@app.route('/set-budget', methods=['GET', 'POST'])
@login_required
def set_budget():
    form = BudgetForm()
    if request.method == 'GET':
        form.limit.data = current_user.monthly_limit
    if form.validate_on_submit():
        current_user.monthly_limit = form.limit.data
        db.session.commit()
        award_achievement(current_user, 'Budget Master')
        flash("Your monthly budget has been saved.", 'success')
        return redirect(url_for('wallet'))
    return render_template('set_budget.html', title='Set Budget', form=form)

@app.route('/set-goal', methods=['GET', 'POST'])
@login_required
def set_goal():
    form = GoalForm()
    if request.method == 'GET':
        form.goal.data = current_user.saving_goal
    if form.validate_on_submit():
        current_user.saving_goal = form.goal.data
        db.session.commit()
        flash("Your savings goal has been saved.", 'success')
        return redirect(url_for('wallet'))
    return render_template('set_goal.html', title='Set Goal', form=form)

@app.route('/recurring', methods=['GET', 'POST'])
@login_required
def recurring_expenses():
    form = RecurringExpenseForm()
    if form.validate_on_submit():
        start_date_obj = datetime.strptime(form.start_date.data, '%Y-%m-%d').date()
        new_recurring_expense = RecurringExpense(user_id=current_user.id, amount=form.amount.data, category=form.category.data, description=form.description.data, frequency=form.frequency.data, start_date=start_date_obj)
        db.session.add(new_recurring_expense)
        db.session.commit()
        if RecurringExpense.query.filter_by(user_id=current_user.id).count() == 1:
            award_achievement(current_user, 'Automator')
        flash('New recurring expense added successfully!', 'success')
        return redirect(url_for('recurring_expenses'))
    user_recurring_expenses = RecurringExpense.query.filter_by(user_id=current_user.id).order_by(RecurringExpense.start_date.desc()).all()
    return render_template('recurring_expenses.html', title='Recurring Expenses', form=form, recurring_expenses=user_recurring_expenses)

@app.cli.command("init-db")
def init_db_command():
    """Creates new tables in the database and adds initial data."""
    db.create_all()
    setup_initial_data()
    print(">>> The database has been successfully initialized. You can now run the application.")

if __name__ == '__main__':

    app.run(debug=True)

