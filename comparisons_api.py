from flask import Blueprint, jsonify, session
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db, Sale, Expense, Customer, User

comparisons_bp = Blueprint('comparisons_bp', __name__)

# =========================================================================
# الاستيرادات الضرورية (يجب التأكد من وجودها في بداية ملف التطبيق الخاص بك)
# =========================================================================
from flask import jsonify, session, Blueprint, current_app as app
from datetime import datetime, timedelta
from sqlalchemy import func

# =========================================================================
# API: بيانات صفحة المقارنات (Endpoint)
# =========================================================================
@comparisons_bp.route('/api/comparisons', methods=['GET'])
def get_comparison_data():
    # 1. التحقق من صلاحية الوصول
    # ملاحظة: إذا كانت جلسات المستخدمين (sessions) غير مستخدمة، يجب تعديل هذا الجزء
    if 'logged_in' not in session or 'user_id' not in session:
        return jsonify({"error": "غير مصرح لك بالوصول. يرجى تسجيل الدخول."}), 401

    user_id = session['user_id']
    
    # محاولة الحصول على بيانات الشركة/المستخدم للفلترة الصحيحة
    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({"error": "بيانات المستخدم غير موجودة."}), 404
        
    company_id = current_user.company_id # افتراض أن الفلترة تكون على مستوى الشركة

    # 2. تحديد الفترات الزمنية
    today = datetime.now().date()
    # تاريخ اليوم الأخير من الشهر الحالي
    end_current = today 
    
    # تاريخ أول يوم في الشهر الحالي
    start_current = today.replace(day=1)
    
    # تاريخ اليوم الأخير من الشهر الماضي
    end_previous = start_current - timedelta(days=1)
    
    # تاريخ أول يوم في الشهر الماضي
    start_previous = end_previous.replace(day=1)
    
    # الحصول على اسم الشهر الحالي والسابق للعرض في الواجهة الأمامية
    current_month_name = start_current.strftime("%B")
    previous_month_name = start_previous.strftime("%B")

    # 3. استعلامات قاعدة البيانات
    
    # (أ) مبيعات الشهر الحالي والماضي (نفترض أن المبيعات مرتبطة بالشركة)
    current_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.sale_date >= start_current,
        Sale.sale_date <= end_current,
        Sale.company_id == company_id # افتراض أن نموذج Sale يحتوي على company_id
    ).scalar()

    previous_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.sale_date >= start_previous,
        Sale.sale_date <= end_previous,
        Sale.company_id == company_id
    ).scalar()

    # (ب) المصروفات الشهرية (نفترض أنها مرتبطة بالشركة)
    current_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.expense_date >= start_current,
        Expense.expense_date <= end_current,
        Expense.company_id == company_id # افتراض أن نموذج Expense يحتوي على company_id
    ).scalar()

    previous_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.expense_date >= start_previous,
        Expense.expense_date <= end_previous,
        Expense.company_id == company_id
    ).scalar()

    # (ج) الأرباح (صافي الربح)
    current_profit = float(current_sales or 0) - float(current_expenses or 0)
    previous_profit = float(previous_sales or 0) - float(previous_expenses or 0)

    # (د) عدد العملاء والموظفين
    # العملاء مرتبطون بالشركة
    customers_count = Customer.query.filter_by(company_id=company_id).count()
    # الموظفون (نفترض أن role='employee' يميزهم عن المدراء/المستخدمين)
    employees_count = User.query.filter_by(company_id=company_id, role='employee').count()
    
    # 4. إرجاع البيانات بصيغة JSON
    return jsonify({
        "sales": {
            "current_month": round(float(current_sales), 2),
            "previous_month": round(float(previous_sales), 2)
        },
        "expenses": { # تمت إضافة بيانات المصروفات للاستفادة منها في الرسم البياني
            "current_month": round(float(current_expenses), 2),
            "previous_month": round(float(previous_expenses), 2)
        },
        "profit": {
            "current_month": round(current_profit, 2),
            "previous_month": round(previous_profit, 2)
        },
        "counts": {
            "customers": customers_count,
            "employees": employees_count
        },
        "month_names": { # لإرسال أسماء الأشهر للواجهة الأمامية
            "current": current_month_name,
            "previous": previous_month_name
        }
    }), 200