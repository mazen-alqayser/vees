import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from flask_login import LoginManager, login_required, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload # لاستخدام joinedload لجلب البيانات المرتبطة
from sqlalchemy import func # هذا هو السطر المفقود
from datetime import datetime
from flask import jsonify, request, Flask # 👈 يجب استيراد Flask
from flask_sqlalchemy import SQLAlchemy # 👈 يجب استيراد SQLAlchemy
from sqlalchemy.orm import joinedload # 👈 قد تحتاجها
# تحميل المتغيرات من ملف .env
load_dotenv()

# تهيئة تطبيق Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'a_default_secret_key_if_not_set')
# تهيئة Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# تحديد صفحة تسجيل الدخول الافتراضية
login_manager.login_view = 'login'  # غيّر الاسم حسب دالة تسجيل الدخول عندك

# تهيئة SQLAlchemy
db = SQLAlchemy(app)

# =========================================================================
# تعريف الجداول (Models) بناءً على جميع التعليمات التي قدمتها
# =========================================================================

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)

    # بيانات الدخول (مطلوبة فقط لو كان مدير/أدمن، الموظف مش هيحتاجها)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    firebase_uid = db.Column(db.String(255), unique=True)
    role = db.Column(db.String(50), nullable=False, default='employee')  # افتراضي: موظف
    contact_info = db.Column(db.String(50))

    # بيانات الموظف
    name = db.Column(db.String(255), nullable=False)
    job_title = db.Column(db.String(255))
    salary = db.Column(db.Numeric(10, 2))
    salary_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    status = db.Column(db.String(50), nullable=False, default='active')
    is_deleted = db.Column(db.Boolean, default=False)

    # ربط الموظفين بالشركة التي ينتمون إليها
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'))
    company = db.relationship("Company", foreign_keys=[company_id], backref="employees")


class Company(db.Model):
    __tablename__ = 'companies'
    company_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(255))
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))

    # هذا هو المفتاح الخارجي الأول، يربط الشركة بمشرفها
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)

    # حقول جديدة من نموذج التسجيل
    country = db.Column(db.String(100))
    secondary_phone = db.Column(db.String(50))
    branches_count = db.Column(db.Integer)
    product_type = db.Column(db.String(50))  # 'products', 'services', 'both'
    expected_users = db.Column(db.String(50))  # '1-5', '6-10', etc.
    purpose = db.Column(db.Text)
    how_heard = db.Column(db.Text)

    # العلاقة التي تربط الشركة بمشرفها (User)
    admin = db.relationship(
        'User',
        foreign_keys=[admin_id],
        backref=db.backref('admin_of_company', uselist=False),
        lazy=True
    )

class Product(db.Model):
    __tablename__ = 'products'
     
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('products', lazy=True))
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    barcode = db.Column(db.String(255), unique=True)
    code = db.Column(db.String(255))
    category = db.Column(db.String(255))
    image_url = db.Column(db.Text)
    quantity_in_stock = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    wholesale_price = db.Column(db.Numeric(10, 2))
    retail_price = db.Column(db.Numeric(10, 2))
    supplier = db.Column(db.String(255))

    def to_dict(self):
        profit_loss = None
        if self.retail_price is not None and self.cost_price is not None:
            profit_loss = (self.retail_price - self.cost_price) * self.quantity_in_stock

        return {
            'id': self.id,
            'name': self.name,
            'barcode': self.barcode,
            'code': self.code,
            'category': self.category,
            'image_url': self.image_url,
            'quantity_in_stock': self.quantity_in_stock,
            'cost_price': float(self.cost_price),
            'wholesale_price': float(self.wholesale_price) if self.wholesale_price is not None else None,
            'retail_price': float(self.retail_price) if self.retail_price is not None else None,
            'supplier': self.supplier,
            'profit_loss': float(profit_loss) if profit_loss is not None else None
        }


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    supplier_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_info = db.Column(db.Text)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    transaction_id = db.Column(db.Integer, primary_key=True)
    transaction_date = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id', ondelete='SET NULL'))
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)

class Sale(db.Model):
    __tablename__ = 'sales'
    sale_id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50))
    amount_paid = db.Column(db.Numeric(10, 2))
    change_amount = db.Column(db.Numeric(10, 2))
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    item_id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.sale_id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_unit = db.Column(db.Numeric(10, 2), nullable=False)
    total_item_price = db.Column(db.Numeric(10, 2), nullable=False)
    
class Return(db.Model):
    __tablename__ = 'returns'
    
    return_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'))
    product = db.relationship('Product', backref=db.backref('returns', lazy=True))
    
    quantity = db.Column(db.Integer, nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    cost_price = db.Column(db.Numeric(10, 2))
    retail_price = db.Column(db.Numeric(10, 2))
    wholesale_price = db.Column(db.Numeric(10, 2))
    image_url = db.Column(db.Text)
    
    # ✨ ربط المرتجع بالمستخدم
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('returns', lazy=True))

    def to_dict(self):
        return {
            "id": self.return_id,
            "code": self.product_id,
            "name": self.product.name if self.product else "منتج محذوف",
            "quantity": self.quantity,
            "cost_price": float(self.cost_price) if self.cost_price else 0,
            "retail_price": float(self.retail_price) if self.retail_price else 0,
            "wholesale_price": float(self.wholesale_price) if self.wholesale_price else 0,
            "reason": self.reason,
            "image_url": self.image_url,
            "return_date": self.return_date.strftime("%Y-%m-%d"),
            "user_id": self.user_id
        }
class Expense(db.Model):
    __tablename__ = 'expenses'
    expense_id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True) 
    user = db.relationship('User', backref=db.backref('expenses', lazy=True))

class ProfitLossReport(db.Model):
    __tablename__ = 'profit_loss_reports'
    report_id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_revenue = db.Column(db.Numeric(10, 2))
    total_expenses = db.Column(db.Numeric(10, 2))
    total_profit_loss = db.Column(db.Numeric(10, 2))

class InventoryReport(db.Model):
    __tablename__ = 'inventory_reports'
    report_id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_capital = db.Column(db.Numeric(10, 2))
    total_profit_loss = db.Column(db.Numeric(10, 2))
    inventory_type = db.Column(db.String(50))

class LowStockAlert(db.Model):
    __tablename__ = 'low_stock_alerts'
    alert_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    alert_date = db.Column(db.Date, nullable=False)
    current_quantity = db.Column(db.Integer, nullable=False)

class TrialBalanceAccount(db.Model):
    __tablename__ = 'trial_balance_accounts'
    account_id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(255), nullable=False)
    debit_balance = db.Column(db.Numeric(10, 2))
    credit_balance = db.Column(db.Numeric(10, 2))

class CashFlowActivity(db.Model):
    __tablename__ = 'cash_flow_activities'
    activity_id = db.Column(db.Integer, primary_key=True)
    activity_name = db.Column(db.String(255), nullable=False)
    cash_flow_amount = db.Column(db.Numeric(10, 2))

class Customer(db.Model):
    __tablename__ = 'customers'
    
    # 1. أعمدة المفتاح والرابط (مؤكد وجودها)
    customer_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('customers', lazy=True))
    
    # 2. بيانات العميل الأخرى (مؤكد وجودها)
    name = db.Column(db.String(255), nullable=False)
    contact_info = db.Column(db.String(255))
    phone = db.Column(db.String(255)) 
    email = db.Column(db.String(255))
    address = db.Column(db.String(255))
    
    # 3. أعمدة الديون الجديدة/المُضافة (التي أضفتها الآن عبر ALTER TABLE)
    total_debt = db.Column(db.Numeric(10, 2), default=0.00) 
    total_paid = db.Column(db.Numeric(10, 2), default=0.00) 
    products_sold_summary = db.Column(db.Text) 

    # 4. التجسيد كقاموس (يجب تحديثها لتعكس الأعمدة الجديدة)
    def to_dict(self):
        return {
            'customer_id': self.customer_id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'contact_info': self.contact_info,
            'user_id': self.user_id,
            # أعمدة الديون المضافة حديثاً
            'products_sold_summary': self.products_sold_summary,
            'total_debt': float(self.total_debt),
            'total_paid': float(self.total_paid),
            'remaining_debt': float(self.total_debt - self.total_paid)
        }
    
# =========================================================================
# مسارات التطبيق (Routes)
# =========================================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# مسار لإنشاء الجداول في قاعدة البيانات
@app.cli.command("create_db")
def create_db():
    """ينشئ جميع الجداول في قاعدة البيانات."""
    db.create_all()
    print("تم إنشاء الجداول بنجاح!")

# مسار لعرض صفحة المشرف
@app.route('/admin')
def admin_panel():
    return render_template('admin.html')
    
# المسار الرئيسي الذي يعيد توجيه المستخدم إلى صفحة تسجيل الدخول
@app.route('/')
def home():
    if 'logged_in' in session:
        return redirect(url_for('index'))
    return redirect(url_for('login'))

# مسار لإظهار صفحة index.html بعد التحقق من تسجيل الدخول
@app.route('/index')
def index():
    if 'logged_in' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

# مسار لإظهار صفحة sales.html
@app.route('/sales')
def sales():
    if 'logged_in' in session:
        return render_template('sales.html')
    return redirect(url_for('login'))

# مسار لإظهار صفحة inventory.html
@app.route('/inventory')
def inventory():
    if 'logged_in' in session:
        return render_template('inventory.html')
    return redirect(url_for('login'))
    
# مسار لإظهار صفحة products.html
@app.route('/products')
def products():
    if 'logged_in' in session:
        return render_template('products.html')
    return redirect(url_for('login'))
    
# مسار لإظهار صفحة returns.html
@app.route('/returns')
def returns():
    if 'logged_in' in session:
        return render_template('returns.html')
    return redirect(url_for('login'))
    
# مسار لإظهار صفحة profit-loss.html
@app.route('/profit-loss')
def profit_loss():
    if 'logged_in' in session:
        return render_template('profit-loss.html')
    return redirect(url_for('login'))
    
# مسار لإظهار صفحة reports.html
@app.route('/reports')
def reports():
    if 'logged_in' in session:
        return render_template('reports.html')
    return redirect(url_for('login'))

# مسار لإظهار صفحة transactions.html
@app.route('/transactions')
def transactions():
    if 'logged_in' in session:
        return render_template('transactions.html')
    return redirect(url_for('login'))

# مسار لعرض صفحة تسجيل الدخول
@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')
# The corrected login route in your Flask backend (app.py)
@app.route('/login', methods=['POST'])
def process_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # ... (التحقق من البيانات وكلمة المرور)

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        if user.status == 'active':
            session['logged_in'] = True
            session['user_id'] = user.id
            session['role'] = user.role

            # **منطق التوجيه الجديد:**
            if user.role == 'super_admin':
                redirect_url = url_for('admin_panel')
            elif user.role == 'company_admin':
                redirect_url = url_for('index')
            else:
                # توجيه افتراضي للحالات غير المتوقعة
                redirect_url = url_for('login')

            return jsonify({"message": "تم تسجيل الدخول بنجاح", "redirect_url": redirect_url}), 200
        elif user.status == 'pending':
            return jsonify({"error": "حسابك قيد المراجعة. يرجى الانتظار حتى يتم تفعيله من قبل المشرف العام."}), 403
        # ... (باقي حالات الأخطاء)

    # ... (باقي حالات الأخطاء)
        elif user.status == 'suspended':
            return jsonify({"error": "تم تعليق حسابك. يرجى التواصل مع الدعم."}), 403
        else:
            return jsonify({"error": "حسابك غير نشط."}), 403
    
    return jsonify({"error": "البريد الإلكتروني أو كلمة المرور غير صحيحة."}), 401
# مسار لتسجيل الخروج
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# مسار لإظهار صفحة register.html
@app.route('/register')
def register():
    return render_template('register.html')
    
# مسار جديد لمعالجة طلب التسجيل (تم تحديثه ومصحح)
@app.route('/api/register', methods=['POST'])
def register_user_and_company():
    from sqlalchemy.exc import IntegrityError # تأكد من استيراد IntegrityError

    try:
        data = request.get_json()
        
        required_fields = ['email', 'password', 'company_name', 'owner_name']
        if not all(data.get(field) for field in required_fields):
            return jsonify({"error": "البيانات غير مكتملة. يرجى ملء جميع الحقول الإلزامية."}), 400

        hashed_password = generate_password_hash(data['password'])
        
        # 1. إنشاء المستخدم أولاً
        new_user = User(
            email=data['email'],
            password_hash=hashed_password,
            name=data['owner_name'],
            job_title="Owner/Admin",
            role="company_admin",
            contact_info=data.get('main_phone'),
            status='pending' # يفضل تفعيل الحساب فور التسجيل إذا كنت لا تحتاج لخطوة موافقة
        )
        db.session.add(new_user)
        db.session.flush() # نستخدم flush للحصول على ID المستخدم (new_user.id)
        
        # 2. إنشاء الشركة وربطها بالمستخدم
        new_company = Company(
            name=data['company_name'],
            industry=data.get('industry'),
            address=data.get('address'),
            phone=data.get('main_phone'),
            admin_id=new_user.id, # ربط الشركة بالـ admin_id
            country=data.get('country'),
            secondary_phone=data.get('additional_phone'),
            branches_count=data.get('branches_count'),
            product_type=data.get('product_type'),
            expected_users=data.get('expected_users'),
            purpose=data.get('purpose'),
            how_heard=data.get('how_heard')
        )
        db.session.add(new_company)
        db.session.flush() # نستخدم flush للحصول على ID الشركة (new_company.company_id)
        
        # 3. **الخطوة المفقودة والأهم: ربط المستخدم بالشركة الجديدة**
        new_user.company_id = new_company.company_id
        
        db.session.commit()

        return jsonify({
            "message": "تم تسجيل حساب الشركة بنجاح.",
            "user_id": new_user.id,
            "company_id": new_company.company_id
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "هذا البريد الإلكتروني مسجل بالفعل."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "حدث خطأ غير متوقع: " + str(e)}), 500
    
# مسار لإظهار صفحة customers.html
@app.route('/customers')
def customers():
    if 'logged_in' in session:
        return render_template('customers.html')
    return redirect(url_for('login'))

# مسار لإظهار صفحة employees.html
@app.route('/employees')
def employees():
    if 'logged_in' in session:
        return render_template('employees.html')
    return redirect(url_for('login'))
    
# مسار لإظهار صفحة forecasts.html
@app.route('/forecasts')
def forecasts():
    if 'logged_in' in session:
        return render_template('forecasts.html')
    return redirect(url_for('login'))
    



# =========================================================================
# مسارات API جديدة لإدارة الموظفين
# =========================================================================
# -------------------------
# إضافة موظف جديد (POST)
# -------------------------
from datetime import datetime # يجب أن يكون هذا السطر موجوداً في بداية ملفك
from datetime import datetime
# تأكد من استيراد generate_password_hash إذا كان نموذجك يتطلبه

@app.route('/api/employees', methods=['POST'])
def add_employee():
    # التحقق من تسجيل الدخول
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401
    
    data = request.get_json()
    user_id = session['user_id']
    company_admin = User.query.get(user_id)

    # ... (كود التحقق من الشركة - صحيح) ...
    if not company_admin or not company_admin.company:
        return jsonify({"error": "المستخدم الحالي غير مرتبط بشركة"}), 404
    
    company_id = company_admin.company.company_id
    
    try:
        # التأكد من توفر البيانات الأساسية
        if not all(k in data for k in ('name', 'email', 'position', 'salary', 'salary_date')):
            raise KeyError 

        # ... (كود تحويل التاريخ والراتب - صحيح) ...
        salary_date_obj = datetime.strptime(data['salary_date'], '%Y-%m-%d').date() 
        salary_for_db = float(data['salary'])
        
        # إنشاء الموظف باستخدام القيم المحولة والقيم الافتراضية للأعمدة الإلزامية
        new_employee = User(
            name=data['name'],
            job_title=data['position'],
            salary=salary_for_db,
            salary_date=salary_date_obj,
            email=data['email'],
            company_id=company_id,
            role='employee',
            
            # **هذه هي الإضافة الحرجة لمنع 500:**
            # 1. تعيين قيمة فارغة أو افتراضية لعمود كلمة المرور الإلزامي
            password_hash='', 
            
            # 2. أضف هنا أي أعمدة أخرى إلزامية (مثل: status, is_active)
            # is_active=True,
            # status='active'
        )
        db.session.add(new_employee)
        db.session.commit()
        
        # ... (بقية كود النجاح - صحيح) ...
        return jsonify({
            "message": "تمت إضافة الموظف بنجاح",
            "employee": {
                 # ... (تفاصيل الموظف) ...
            }
        }), 201
        
    except KeyError:
        return jsonify({"error": "البيانات غير مكتملة. يرجى ملء جميع الحقول الإلزامية."}), 400
    except ValueError:
        return jsonify({"error": "قيمة الراتب أو تنسيق التاريخ غير صالح."}), 400
    except Exception as e:
        db.session.rollback()
        # **الآن، ركز على الرسالة في CMD**
        return jsonify({"error": f"حدث خطأ غير متوقع في الخادم: {str(e)}"}), 500
# -------------------------
# جلب كل الموظفين (GET)
# -------------------------

@app.route('/api/employees', methods=['GET'])
def list_employees():
    # التحقق من تسجيل الدخول
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك"}), 401

    user_id = session['user_id']
    current_user = User.query.get(user_id)

    # 1. جلب company_id للمستخدم الحالي
    if not current_user or not current_user.company:
        # هذه الحالة قد تحدث إذا كان المستخدم super_admin غير مرتبط بشركة
        if current_user and current_user.role == 'super_admin':
            # إذا كان مشرف عام، يمكنك السماح له برؤية كل شيء أو إعطاء قائمة فارغة حسب متطلباتك
            employees = User.query.filter(User.role.in_(['employee', 'company_admin'])).all()
        else:
            return jsonify({"error": "المستخدم غير مرتبط بشركة لعرض موظفيها"}), 404
    else:
        company_id = current_user.company.company_id

        # 2. الاستعلام الصحيح: جلب كل مستخدمي الشركة الذين هم موظفون أو مدراء
        employees = User.query.filter(
            User.company_id == company_id,
            User.role.in_(['employee', 'company_admin'])
        ).all()
    
    # 3. إعادة البيانات بصيغة JSON
    return jsonify([{
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "position": emp.job_title,
        "salary": float(emp.salary) if emp.salary else None,
        # تحويل التاريخ إلى تنسيق ISO string إذا لم يكن None
        "salary_date": emp.salary_date.isoformat() if emp.salary_date else None
    } for emp in employees])
# -------------------------
# تحديث بيانات موظف (PUT)
# -------------------------
from datetime import datetime

from datetime import datetime # تأكد من استيراد هذه المكتبة

@app.route('/api/employees/<int:employee_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_employee(employee_id):
    # 1. التحقق من تسجيل الدخول
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    user_id = session['user_id']
    current_user = User.query.get(user_id)
    
    # تحديد ID الشركة للمستخدم الحالي
    if not current_user or not current_user.company:
        return jsonify({"error": "المستخدم الحالي غير مرتبط بشركة"}), 404
        
    company_id = current_user.company.company_id

    # 2. جلب الموظف بالاعتماد على ID الموظف و ID الشركة (للصلاحية)
    employee = User.query.filter_by(id=employee_id, company_id=company_id).first()
    if not employee:
        return jsonify({"error": "الموظف غير موجود أو ليس لديك صلاحية"}), 404

    # ----------------------------------------------------
    # A) معالجة طلب GET (جلب البيانات) - هذا هو ما كان مفقودًا
    # ----------------------------------------------------
    if request.method == 'GET':
        return jsonify({
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "position": employee.job_title,
            "salary": float(employee.salary) if employee.salary else None,
            # إرجاع التاريخ بتنسيق ISO 8601 المطلوب للـ Frontend
            "salary_date": employee.salary_date.isoformat() if employee.salary_date else None
        }), 200

    # ----------------------------------------------------
    # B) معالجة طلب PUT (تحديث البيانات)
    # ----------------------------------------------------
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            employee.name = data.get('name', employee.name)
            employee.job_title = data.get('position', employee.job_title)
            
            # معالجة الراتب بأمان
            salary_data = data.get('salary')
            if salary_data is not None:
                try:
                    employee.salary = float(salary_data)
                except (ValueError, TypeError):
                    return jsonify({"error": "قيمة الراتب غير صالحة."}), 400

            # معالجة حقل التاريخ بأمان
            if data.get('salary_date'):
                try:
                    salary_date = datetime.strptime(data['salary_date'], '%Y-%m-%d').date()
                    employee.salary_date = salary_date
                except ValueError:
                    return jsonify({"error": "تنسيق التاريخ غير صالح. يجب أن يكون YYYY-MM-DD."}), 400

            employee.email = data.get('email', employee.email)
            
            db.session.commit()
            return jsonify({"message": "تم تحديث بيانات الموظف بنجاح"}), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"حدث خطأ أثناء التحديث: {str(e)}"}), 500

    # ----------------------------------------------------
    # C) معالجة طلب DELETE (حذف الموظف)
    # ----------------------------------------------------
    elif request.method == 'DELETE':
        try:
            # التأكد من عدم محاولة حذف مدير الشركة نفسه (ميزة أمان)
            if employee.id == user_id:
                 return jsonify({"error": "لا يمكن حذف حساب المدير النشط. قم بتعيين مدير جديد أولاً."}), 403

            db.session.delete(employee)
            db.session.commit()
            return jsonify({"message": "تم حذف الموظف بنجاح"}), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"حدث خطأ أثناء الحذف: {str(e)}"}), 500
        
# =========================================================================
# API: إضافة عميل جديد
@app.route('/api/customers', methods=['POST'])
def add_new_customer():
    # ... (التحقق من تسجيل الدخول والـ session) ...
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        
        # التأكد من تحويل القيم الرقمية، واستخدام 0.00 كقيمة افتراضية إذا كانت مفقودة
        debt = float(data.get('initial_debt', 0.00)) 
        paid = float(data.get('initial_paid', 0.00)) 

        if not data.get('name'):
            return jsonify({"error": "اسم العميل إلزامي."}), 400

        new_customer = Customer(
            user_id=user_id,
            name=data['name'],
            
            # 🚨 الأعمدة الجديدة المضافة إلى الحفظ (لإكمال السجل)
            phone=data.get('phone'),    # يجب إضافة هذا
            email=data.get('email'),    # يجب إضافة هذا
            address=data.get('address'),# يجب إضافة هذا

            # الأعمدة القديمة
            contact_info=data.get('contact_info'),
            products_sold_summary=data.get('products_sold_summary'),
            
            # أعمدة الديون
            total_debt=debt, 
            total_paid=paid
            
            # ملاحظة: إذا كان لديك عمود 'created_at' في كلاس Customer، لا تحتاج لتمريره هنا لأنه يتم تعيينه تلقائياً.
        )
        
        db.session.add(new_customer)
        db.session.commit()
        
        return jsonify({"message": "تم إضافة العميل بنجاح.", "customer": new_customer.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        # 🚨 اطبع الخطأ الكامل هنا لتحديد المشكلة بالضبط إذا استمرت
        print("Error during customer addition (POST 500):", str(e))
        return jsonify({"error": f"حدث خطأ غير متوقع: {str(e)}"}), 500
### 2.2. جلب جميع العملاء (GET)
# API: جلب جميع عملاء المستخدم الحالي
@app.route('/api/customers', methods=['GET'])
def get_all_customers():
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    user_id = session['user_id']
    
    # جلب جميع العملاء المرتبطين بمعرّف المستخدم الحالي فقط
    customers = Customer.query.filter_by(user_id=user_id).all()
    
    return jsonify([c.to_dict() for c in customers]), 200

### 2.3. تحديث دين العميل (PUT)

from decimal import Decimal, InvalidOperation

# API: جلب أو تحديث عميل محدد
@app.route('/api/customers/<int:customer_id>', methods=['GET', 'PUT'])
def manage_customer_debt(customer_id):
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    user_id = session['user_id']
    
    # جلب العميل والتأكد من أنه يخص المستخدم الحالي
    customer = Customer.query.filter_by(customer_id=customer_id, user_id=user_id).first()
    
    if not customer:
        return jsonify({"error": "العميل غير موجود أو ليس لديك صلاحية"}), 404

    # ----------------------------------------------------
    # GET: جلب تفاصيل العميل لعرضها
    # ----------------------------------------------------
    if request.method == 'GET':
        return jsonify(customer.to_dict()), 200

    # ----------------------------------------------------
    # PUT: تحديث الديون (إضافة دين جديد أو تسجيل تسديد)
    # ----------------------------------------------------
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            
            # إضافة دين جديد: يتم إرسال 'new_debt_amount'
            if 'new_debt_amount' in data and data['new_debt_amount'] is not None:
                new_debt = Decimal(str(data['new_debt_amount']))
                if new_debt < 0:
                    return jsonify({"error": "قيمة الدين الجديدة يجب أن تكون موجبة."}), 400
                # إضافة المبلغ الجديد إلى إجمالي الدين
                customer.total_debt += new_debt
                
            # تسجيل تسديد: يتم إرسال 'payment_amount'
            if 'payment_amount' in data and data['payment_amount'] is not None:
                payment = Decimal(str(data['payment_amount']))
                if payment < 0:
                    return jsonify({"error": "قيمة التسديد يجب أن تكون موجبة."}), 400
                # إضافة المبلغ المسدد إلى إجمالي المسدد
                customer.total_paid += payment
                
            # تحديث حقول أخرى (مثل الاسم أو المنتجات) بشكل اختياري
            customer.name = data.get('name', customer.name)
            customer.products_sold_summary = data.get('products_sold_summary', customer.products_sold_summary)

            db.session.commit()
            return jsonify({"message": "تم تحديث بيانات الدين/العميل بنجاح.", "customer": customer.to_dict()}), 200

        except (ValueError, InvalidOperation):
            db.session.rollback()
            return jsonify({"error": "قيمة المبلغ المرسلة غير صالحة."}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"حدث خطأ أثناء التحديث: {str(e)}"}), 500

        # API: حذف عميل
@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    user_id = session['user_id']
    customer = Customer.query.filter_by(customer_id=customer_id, user_id=user_id).first()

    if not customer:
        return jsonify({"error": "العميل غير موجود أو ليس لديك صلاحية"}), 404

    try:
        db.session.delete(customer)
        db.session.commit()
        return jsonify({"message": "تم حذف العميل بنجاح."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"فشل حذف العميل: {str(e)}"}), 500

# =========================================================================


# مسار لإظهار صفحة comparisons.html
@app.route('/comparisons')
def comparisons():
    if 'logged_in' in session:
        return render_template('comparisons.html')
    return redirect(url_for('login'))


from werkzeug.security import generate_password_hash
from app import app, db, User # تأكد من استيراد User

@app.cli.command('create_super_admin')
def create_super_admin_command():
    """Creates a super admin user."""
    email = input("Enter admin email: ")
    password = input("Enter admin password: ")
    
    # تحقق من وجود المستخدم مسبقًا
    existing_admin = User.query.filter_by(email=email).first()
    if existing_admin:
        print("Error: A user with this email already exists.")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    new_admin = User(
        email=email,
        password_hash=hashed_password,
        role='super_admin'
    )
    db.session.add(new_admin)
    db.session.commit()
    print(f"Super admin account created successfully for {email}")

# =========================================================================
# مسارات API للواجهة الأمامية
# =========================================================================

# API: جلب جميع المنتجات
@app.route('/api/products', methods=['GET'])
def get_products():
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    user_id = session['user_id']
    products = Product.query.filter_by(user_id=user_id).all()
    return jsonify([p.to_dict() for p in products])

# API: إضافة منتج جديد
@app.route('/api/products', methods=['POST'])
def add_product():
    # Check if a user is logged in before allowing them to add a product
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    try:
        data = request.get_json()
        user_id = session['user_id'] # Retrieve the current user's ID from the session
        
        # Ensure all required fields are present
        required_fields = ['name', 'quantity_in_stock', 'cost_price']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "بيانات المنتج غير مكتملة."}), 400

        new_product = Product(
            name=data['name'],
            barcode=data.get('barcode'),
            code=data.get('code'),
            category=data.get('category'),
            image_url=data.get('image_url'),
            quantity_in_stock=data['quantity_in_stock'],
            cost_price=data['cost_price'],
            wholesale_price=data.get('wholesale_price'),
            retail_price=data.get('retail_price'),
            supplier=data.get('supplier'),
            user_id=user_id # **Associate the product with the user ID**
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify(new_product.to_dict()), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "المنتج موجود بالفعل، يرجى التحقق من الباركود."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "حدث خطأ غير متوقع: " + str(e)}), 500
# API: تحديث منتج موجود
@app.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):

    # تحقق من أن المستخدم مسجل دخوله
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401

    try:
        user_id = session['user_id']
        # ابحث عن المنتج باستخدام ID المنتج و ID المستخدم
        product = Product.query.filter_by(id=id, user_id=user_id).first()
        
        # إذا لم يتم العثور على المنتج، فهذا يعني إما أنه غير موجود أو لا ينتمي للمستخدم الحالي
        if not product:
            return jsonify({"error": "المنتج غير موجود أو ليس لديك صلاحية لتعديله."}), 404

        data = request.get_json()
        
        # تحديث الحقول
        product.name = data.get('name', product.name)
        product.barcode = data.get('barcode', product.barcode)
        product.code = data.get('code', product.code)
        product.category = data.get('category', product.category)
        product.image_url = data.get('image_url', product.image_url)
        product.quantity_in_stock = data.get('quantity_in_stock', product.quantity_in_stock)
        product.cost_price = data.get('cost_price', product.cost_price)
        product.wholesale_price = data.get('wholesale_price', product.wholesale_price)
        product.retail_price = data.get('retail_price', product.retail_price)
        product.supplier = data.get('supplier', product.supplier)

        db.session.commit()
        return jsonify(product.to_dict()), 200
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "المنتج موجود بالفعل، يرجى التحقق من الباركود."}), 409
    except Exception as e:
        db.session.rollback()
    
    return jsonify({"error": "حدث خطأ غير متوقع: " + str(e)}), 500

# API: حذف منتج
@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    # الخطوة 1: تحقق من أن المستخدم مسجل دخوله
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401
    
    try:
        user_id = session['user_id']
        
        # الخطوة 2: ابحث عن المنتج باستخدام ID المنتج و ID المستخدم
        # هذا يضمن أن المستخدم لا يمكنه حذف إلا منتجاته الخاصة
        product = Product.query.filter_by(id=id, user_id=user_id).first()
        
        # الخطوة 3: إذا لم يتم العثور على المنتج، أرسل رسالة خطأ
        if not product:
            return jsonify({"error": "المنتج غير موجود أو ليس لديك صلاحية لحذفه."}), 404

        # الخطوة 4: إذا تم العثور على المنتج، قم بحذفه من قاعدة البيانات
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "تم حذف المنتج بنجاح."}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "حدث خطأ غير متوقع: " + str(e)}), 500
    
# API: إتمام عملية بيع
@app.route('/api/sales', methods=['POST'])
def process_sale():
    try:
        sale_data = request.get_json()
        cart_items = sale_data['cart']
        total_amount = sale_data['total_amount']
        payment_method = sale_data['payment_method']
        amount_paid = sale_data.get('amount_paid')
        change_amount = sale_data.get('change_amount')

        # إنشاء سجل بيع جديد
        new_sale = Sale(
            total_amount=total_amount,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_amount=change_amount
            # يمكن إضافة employee_id لاحقاً
        )
        db.session.add(new_sale)
        db.session.flush()  # للحصول على sale_id قبل commit

        # معالجة عناصر سلة المشتريات
        for item in cart_items:
            product = Product.query.get(item['id'])
            if not product or product.quantity_in_stock < item['quantity']:
                db.session.rollback()
                return jsonify({"error": f"الكمية غير متوفرة للمنتج {item['name']}"}), 400

            # تحديث المخزون
            product.quantity_in_stock -= item['quantity']

            # إضافة عنصر البيع
            sale_item = SaleItem(
                sale_id=new_sale.sale_id,
                product_id=product.id,
                quantity=item['quantity'],
                price_per_unit=item['retail_price'],
                total_item_price=item['retail_price'] * item['quantity']
            )
            db.session.add(sale_item)

        db.session.commit()
        return jsonify({"message": "تم إتمام عملية البيع بنجاح.", "sale_id": new_sale.sale_id}), 201

    except KeyError:
        db.session.rollback()
        return jsonify({"error": "البيانات غير مكتملة"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
# API: جلب تفاصيل منتج معين
@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'barcode': product.barcode,
        'image_url': product.image_url,
        'quantity_in_stock': product.quantity_in_stock,
        'cost_price': product.cost_price,
        'retail_price': product.retail_price,
        'wholesale_price': product.wholesale_price
    })

# مسار لإضافة مستخدم جديد
@app.route('/api/users/add', methods=['POST'])
def add_user():
    data = request.get_json()
    new_user = User(
        email=data['email'],
        password_hash=data['password_hash'],
        role=data['role'],
        name=data.get('name'),
        contact_info=data.get('contact_info')
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "تم إضافة المستخدم بنجاح!"}), 201
# API: عدد الموظفين
@app.route('/api/employees/count', methods=['GET'])
def get_employees_count():
    count = User.query.filter_by(role="employee").count()
    return jsonify({"count": count})


# API: عدد المنتجات
@app.route('/api/products/count', methods=['GET'])
def get_products_count():
    count = Product.query.count()
    return jsonify({"count": count})
# API: تقرير الأرباح والخسائر للشهر الماضي
from datetime import datetime, timedelta # تأكد من أن هذا الاستيراد موجود في بداية ملف app.py

# =========================================================================
# دوال المساعدة الداخلية لحساب الأرباح والخسائر
# =========================================================================

def calculate_cogs_for_user(user_id, start_date, end_date):
    """تحسب تكلفة البضاعة المباعة (COGS) بناءً على المستخدم والفترة."""
    
    # يجب أن نضمن أن سعر التكلفة المأخوذ من جدول Product هو للمنتجات المباعة 
    # خلال الفترة المحددة، والتي يمتلكها المستخدم الحالي (user_id).
    
    cogs_result = db.session.query(
        func.coalesce(func.sum(
            SaleItem.quantity * Product.cost_price
        ), 0)
    ).join(Sale, SaleItem.sale_id == Sale.sale_id).join(Product, SaleItem.product_id == Product.id).filter(
        Sale.sale_date.between(start_date, end_date),
        Product.user_id == user_id 
    ).scalar() 
    
    # التحويل إلى float لضمان التنسيق الصحيح للـ JSON
    return float(cogs_result)

# =========================================================================
# مسار API: الأرباح والخسائر (/api/profit_loss)
# =========================================================================

@app.route('/api/profit_loss', methods=['GET'])
def get_profit_loss():
    # 1. التحقق من تسجيل الدخول وتحديد المستخدم
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول"}), 401
    
    user_id = session['user_id']
    
    # 2. تحديد الفترة الزمنية
    period_type = request.args.get('period', 'month')
    start_date = None
    end_date = None
    period_label = "الشهر الماضي"
    
    # 💥 التعديل هنا: استدعاء datetime.now() مباشرة بعد الاستيراد "from datetime import datetime"
    today = datetime.now().date()
    
    try:
        if period_type == 'month':
            start_of_current_month = today.replace(day=1)
            # 💥 التعديل هنا: استخدام timedelta مباشرة بعد الاستيراد "from datetime import timedelta"
            end_date = start_of_current_month - timedelta(days=1) 
            start_date = end_date.replace(day=1)
        elif period_type == 'year':
            start_of_current_year = today.replace(month=1, day=1)
            # 💥 التعديل هنا: استخدام timedelta مباشرة
            end_date = start_of_current_year - timedelta(days=1)
            start_date = end_date.replace(month=1, day=1)
            period_label = "العام الماضي"
        elif period_type == 'custom':
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            # 💥 التعديل هنا: استخدام datetime.strptime مباشرة
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period_label = f"من {start_date_str} إلى {end_date_str}"
        
        if not start_date or not end_date:
            return jsonify({"error": "فترة زمنية غير محددة"}), 400

    except Exception as e:
        # إذا فشل التحويل التاريخي، يجب أن يعود بخطأ 400
        return jsonify({"error": f"خطأ في معالجة التاريخ أو تنسيقه: {str(e)}"}), 400


    # 3. جلب البيانات المالية مع الفلترة حسب المستخدم (user_id)
    
    # (أ) إجمالي الإيرادات (المبيعات الفعلية)
    total_revenue = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).join(SaleItem, SaleItem.sale_id == Sale.sale_id).join(Product, SaleItem.product_id == Product.id).filter(
        Sale.sale_date.between(start_date, end_date),
        Product.user_id == user_id 
    ).scalar()
    
    # (ب) تكلفة البضاعة المباعة (COGS) - باستخدام الدالة المساعدة
    total_cogs = calculate_cogs_for_user(user_id, start_date, end_date) 
    
    # (ج) إجمالي المصروفات 
    total_expenses = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.expense_date.between(start_date, end_date),
        Expense.user_id == user_id 
    ).scalar()
    
    
    # تحويل النتائج إلى أرقام عشرية
    total_revenue = float(total_revenue)
    total_cogs = float(total_cogs)
    total_expenses = float(total_expenses) 
    
    # 4. حساب صافي الربح
    net_profit_loss = total_revenue - total_cogs - total_expenses
    
    # 5. إرجاع النتيجة
    return jsonify({
        "period_label": period_label,
        "total_revenue": round(total_revenue, 2),
        "total_cogs": round(total_cogs, 2),
        "total_expenses": round(total_expenses, 2),
        "net_profit_loss": round(net_profit_loss, 2)
    })

# داخل كود Flask (مثلاً في app.py)
from datetime import datetime, timedelta
import random
from flask import jsonify

@app.route('/api/forecasts', methods=['GET'])
def get_forecasts():
    today = datetime.today()
    months = []
    profits = []

    # قيمة افتراضية كبداية (ممكن تربطها بمبيعاتك الفعلية لاحقاً من DB)
    current_profit = 40000  

    for i in range(6):
        next_month = today + timedelta(days=30 * i)
        month_name = next_month.strftime("%B")  # اسم الشهر بالإنجليزية
        # توقع بزيادة منطقية 5% - 15%
        growth = random.uniform(1.05, 1.15)
        current_profit = int(current_profit * growth)
        months.append(month_name)
        profits.append(current_profit)

    return jsonify({"months": months, "profits": profits})

# ------------------ API للمعاملات ------------------
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "غير مصرح لك بالوصول. سجل الدخول أولاً."}), 401

    user_id = session['user_id']

    # ✅ المرتجعات
    returns = Return.query.filter_by(user_id=user_id).all()
    returns_list = [dict(r.to_dict(), type="return") for r in returns]

    # ✅ المبيعات
    sales = Sale.query.all()  # ما عندك user_id داخل المبيعات، فنجيبها كلها مؤقتًا
    sales_list = []
    for s in sales:
        sale_dict = {
            "id": getattr(s, "sale_id", None),
            "date": s.sale_date.strftime("%Y-%m-%d") if s.sale_date else "—",
            "details": f"عملية بيع بمبلغ {float(s.total_amount):,.2f} ج.م",
            "amount": float(s.total_amount) if s.total_amount else 0,
            "type": "sale"
        }
        sales_list.append(sale_dict)

    # ✅ الجرد (في حال كان موجود)
    try:
        inventory_ops = InventoryReport.query.all()
    except:
        inventory_ops = []
    inventory_list = []
    for i in inventory_ops:
        inventory_list.append({
            "id": getattr(i, "report_id", None),
            "date": i.end_date.strftime("%Y-%m-%d") if i.end_date else "—",
            "details": f"تقرير جرد ({i.inventory_type or 'عام'})",
            "amount": float(i.total_capital or 0),
            "type": "inventory"
        })

    # ✅ الديون (من العملاء)
    customers = Customer.query.filter_by(user_id=user_id).all()
    debts_list = []
    for c in customers:
        # نضيف فقط العملاء اللي عندهم دين غير صفري
        if hasattr(c, "debt") and c.debt and float(c.debt) > 0:
            debts_list.append({
                "id": getattr(c, "id", None),
                "date": getattr(c, "updated_at", None).strftime("%Y-%m-%d") if hasattr(c, "updated_at") and c.updated_at else "—",
                "details": f"دين على العميل: {c.name}",
                "amount": float(c.debt),
                "type": "debt"
            })

    # ✅ دمج الكل
    transactions = returns_list + sales_list + inventory_list + debts_list

    # ✅ ترتيب حسب التاريخ (تنازلي)
    transactions.sort(key=lambda x: x.get("date", ""), reverse=True)

    return jsonify(transactions), 200
# =========================

# جلب جميع المرتجعات (GET /api/returns)
@app.route('/api/returns', methods=['GET'])
def get_returns():
    # التحقق من تسجيل الدخول
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "غير مصرح لك بالوصول. سجل الدخول أولاً."}), 401

    # 🧩 جلب المرتجعات الخاصة بالمستخدم الحالي فقط
    user_id = session.get('user_id')
    returns = Return.query.filter_by(user_id=user_id).all()

    data = [r.to_dict() for r in returns]
    return jsonify(data), 200


# =========================
# إضافة مرتجع جديد (POST /api/returns)
# =========================
@app.route('/api/returns', methods=['POST'])
def add_return():
    """ يسجل مرتجعًا جديدًا ويحدث مخزون المنتج. """
    data = request.get_json()

    # ✅ تحقق من تسجيل الدخول قبل أي إجراء
    if 'user_id' not in session:
        return jsonify({"error": "يجب تسجيل الدخول أولاً."}), 401

    current_user_id = session['user_id']

    # ✅ الحقول الإلزامية المطلوبة من الواجهة الأمامية
    required_fields = ['name', 'code', 'quantity', 'cost_price', 'retail_price', 'wholesale_price']
    if not all(field in data for field in required_fields):
        missing_fields = [field for field in required_fields if field not in data]
        error_msg = f"البيانات المدخلة غير كاملة. الحقول المفقودة: {', '.join(missing_fields)}"
        print(f"ERROR 400: Missing required fields: {error_msg}")
        return jsonify({"error": error_msg}), 400

    product_code = data['code']

    # ✅ تحويل القيم الرقمية
    try:
        quantity = int(data['quantity'])
        cost_price = float(data['cost_price'])
        retail_price = float(data['retail_price'])
        wholesale_price = float(data['wholesale_price'])
    except (ValueError, TypeError):
        return jsonify({"error": "الكمية والأسعار يجب أن تكون أرقاماً صحيحة."}), 400

    # ✅ التأكد من أن الكمية موجبة
    if quantity <= 0:
        return jsonify({"error": "الكمية المرتجعة يجب أن تكون موجبة."}), 400

    # ✅ البحث عن المنتج الحالي بناءً على (الكود + المستخدم)
    product = Product.query.filter_by(code=product_code, user_id=current_user_id).first()

    if product:
        # ✅ المنتج موجود، نحدث الكمية
        product.quantity_in_stock += quantity
        product_id_for_return = product.id
    else:
        # ✅ المنتج غير موجود — ننشئه جديدًا
        try:
            new_product = Product(
                name=data['name'],
                quantity_in_stock=quantity,
                cost_price=cost_price,
                retail_price=retail_price,
                wholesale_price=wholesale_price,
                image_url=data.get('image_url'),
                user_id=current_user_id,
                code=product_code
            )
            db.session.add(new_product)
            db.session.flush()  # للحصول على ID المنتج الجديد
            product_id_for_return = new_product.id
        except Exception as e:
            db.session.rollback()
            print(f"❌ فشل إنشاء منتج جديد: {e}")
            return jsonify({"error": f"فشل إضافة المنتج الجديد إلى قاعدة البيانات: {e}"}), 500

    # ✅ إنشاء سجل المرتجع الجديد
    new_return = Return(
        product_id=product_id_for_return,
        quantity=quantity,
        cost_price=cost_price,
        retail_price=retail_price,
        wholesale_price=wholesale_price,
        reason=data.get('reason', ''),
        image_url=data.get('image_url'),
        return_date=datetime.utcnow().date(),
        user_id=current_user_id
    )
    db.session.add(new_return)

    try:
        db.session.commit()
        print(f"✅ تم تسجيل مرتجع جديد بنجاح للمستخدم ID={current_user_id}")
        return jsonify({"message": "تم تسجيل المرتجع بنجاح", "id": new_return.return_id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ قاعدة بيانات أثناء الحفظ: {e}")
        return jsonify({"error": "فشل الحفظ في قاعدة البيانات. يرجى المحاولة لاحقاً."}), 500


# =========================
# تعديل مرتجع (PUT /api/returns/<int:return_id>)
# =========================
@app.route('/api/returns/<int:return_id>', methods=['PUT'])
def update_return(return_id):
    """ تعديل بيانات مرتجع موجود، مع تحديث المخزون إن لزم الأمر. """
    r = Return.query.get(return_id)
    if not r:
        return jsonify({"error": "المرتجع غير موجود"}), 404

    data = request.get_json()
    
    # حفظ الكمية القديمة قبل التحديث لحساب فرق المخزون
    old_quantity = r.quantity 
    
    try:
        new_quantity = int(data['quantity'])
        new_product_id = int(data['code']) 
    except (KeyError, ValueError):
        return jsonify({"error": "بيانات الكمية أو رمز المنتج مفقودة أو غير صحيحة."}), 400
    if new_quantity <= 0:
        return jsonify({"error": "الكمية يجب أن تكون موجبة."}), 400
    # 1. تحديث سجل المرتجع
    r.product_id = new_product_id
    r.quantity = new_quantity
    r.cost_price = float(data.get('cost_price', r.cost_price))
    r.retail_price = float(data.get('retail_price', r.retail_price))
    r.wholesale_price = float(data.get('wholesale_price', r.wholesale_price))
    r.reason = data.get('reason', r.reason)
    r.image_url = data.get('image_url', r.image_url)

    # 2. تعديل مخزون المنتج
    old_product = Product.query.get(r.product_id)
    if old_product:
        old_product.quantity_in_stock -= old_quantity

    new_product = Product.query.get(new_product_id)
    if new_product:
        new_product.quantity_in_stock += new_quantity
        
    db.session.commit()
    return jsonify({"message": "تم تحديث المرتجع بنجاح"}), 200


# =========================
# حذف مرتجع (DELETE /api/returns/<int:return_id>)
# =========================
@app.route('/api/returns/<int:return_id>', methods=['DELETE'])
def delete_return(return_id):
    """ يحذف مرتجع ويعكس تأثيره على مخزون المنتج. """
    r = Return.query.get(return_id)
    if not r:
        return jsonify({"error": "المرتجع غير موجود"}), 404
        
    # 1. تحديث مخزون المنتج (عكس عملية الإرجاع)
    product = Product.query.get(r.product_id)
    if product:
        product.quantity_in_stock -= r.quantity
        
    # 2. حذف سجل المرتجع
    db.session.delete(r)
    db.session.commit()
    
    return jsonify({"message": "تم حذف المرتجع بنجاح"}), 200

# =========================
# تسجيل Blueprint للمقارنات
from comparisons_api import comparisons_bp
app.register_blueprint(comparisons_bp)

# =========================================================================
# مسارات API جديدة للوحة تحكم المشرف (Admin Panel)
# =========================================================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email, role='super_admin').first()
    
    if user and check_password_hash(user.password_hash, password):
        session['logged_in'] = True
        session['user_id'] = user.id
        session['role'] = 'super_admin'
        return jsonify({"message": "تم تسجيل الدخول بنجاح"}), 200
    
    return jsonify({"error": "بيانات الاعتماد غير صحيحة"}), 401

@app.route('/api/admin/users', methods=['GET'])
def get_admin_users():
    # جلب جميع المستخدمين مع بيانات الشركة المرتبطة بهم
    users_with_companies = db.session.query(User, Company).outerjoin(Company, User.id == Company.admin_id).all()

    users_data = []
    for user, company in users_with_companies:
        user_info = {
            'id': user.id,
            'email': user.email,
            'ownerName': user.name,
            'status': user.status,
            'is_deleted': user.is_deleted,
            'companyName': company.name if company else None,
            'country': company.country if company else None,
            'primaryPhone': company.phone if company else None,
            'secondaryPhone': company.secondary_phone if company else None,
            'address': company.address if company else None,
            'businessField': company.industry if company else None,
            'branchesCount': company.branches_count if company else None,
            'productType': company.product_type if company else None,
            'expectedUsers': company.expected_users if company else None,
            'purpose': company.purpose if company else None,
            'howHeard': company.how_heard if company else None
        }
        users_data.append(user_info)

    return jsonify(users_data)

@app.route('/api/admin/users/stats', methods=['GET'])
def get_user_stats():
    total_users = User.query.filter_by(is_deleted=False, role='admin').count()
    active_users = User.query.filter_by(status='active', is_deleted=False, role='admin').count()
    suspended_users = User.query.filter_by(status='suspended', is_deleted=False, role='admin').count()
    pending_users = User.query.filter_by(status='pending', is_deleted=False, role='admin').count()
    
    return jsonify({
        'total': total_users,
        'active': active_users,
        'suspended': suspended_users,
        'pending': pending_users
    })

@app.route('/api/admin/users/<int:user_id>/status', methods=['PUT'])
def update_user_status(user_id):
    data = request.get_json()
    new_status = data.get('status')
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404
    
    user.status = new_status
    db.session.commit()
    return jsonify({"message": f"تم تحديث حالة المستخدم إلى {new_status}"}), 200

@app.route('/api/admin/users/<int:user_id>/delete', methods=['PUT'])
def soft_delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404
    
    user.is_deleted = True
    user.status = 'محذوف مؤقتاً'
    db.session.commit()
    return jsonify({"message": "تم حذف المستخدم مؤقتاً"}), 200

@app.route('/api/admin/users/<int:user_id>/restore', methods=['PUT'])
def restore_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404
    
    user.is_deleted = False
    user.status = 'active'
    db.session.commit()
    return jsonify({"message": "تم استعادة المستخدم بنجاح"}), 200

@app.route('/api/admin/users/<int:user_id>/edit', methods=['PUT'])
def edit_user(user_id):
    data = request.get_json()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404
    
    new_email = data.get('email')
    new_password = data.get('password')
    
    if new_email:
        user.email = new_email
    if new_password:
        user.password_hash = generate_password_hash(new_password)
    
    db.session.commit()
    return jsonify({"message": "تم تحديث بيانات المستخدم بنجاح"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
