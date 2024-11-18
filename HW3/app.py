from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import InputRequired, Length
import requests
import traceback
import datetime
import os
from dotenv import load_dotenv
from flask_caching import Cache  # 添加缓存套件

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # 从环境变量中读取密钥

# 设置加密和登录管理
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page."

# 初始化缓存
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
# 可调整 CACHE_DEFAULT_TIMEOUT 以设置默认的缓存时间

# MongoDB 连接
MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client['my_database']  # 替换成你的数据库名称
users_collection = db['users']  # 用户数据的集合
logs_collection = db['startup_log']  # 日志数据的集合

# 创建管理员账号
admin_account = users_collection.find_one({'username': 'admin'})
if not admin_account:
    hashed_password = bcrypt.generate_password_hash("Ab921218").decode('utf-8')
    users_collection.insert_one({'_id': 'admin', 'username': 'admin', 'password': hashed_password, 'is_admin': True})

# Binance API URL
BASE_URL = 'https://data-api.binance.vision'

class User(UserMixin):
    def __init__(self, user_id, username, is_admin=False):
        self.id = user_id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": user_id})
    if user_data:
        return User(user_id=user_data['_id'], username=user_data['username'], is_admin=user_data.get('is_admin', False))
    return None

# 表单定义
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=3, max=15)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=6)])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=3, max=15)])
    password = PasswordField('Password', validators=[InputRequired()])

# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data.strip()

        if users_collection.find_one({'_id': username}):
            flash("Username already exists!", "error")
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user_id = username  # 使用用户名作为自定义的 _id
        users_collection.insert_one({'_id': user_id, 'username': username, 'password': hashed_password, 'is_admin': False})
        login_user(User(user_id=user_id, username=username))
        flash("Registration successful!", "success")
        return redirect(url_for('index'))

    return render_template('register.html', form=form)

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data.strip()

        user_data = users_collection.find_one({'_id': username})
        if user_data:
            if bcrypt.check_password_hash(user_data['password'], password):
                user = User(user_id=user_data['_id'], username=username, is_admin=user_data.get('is_admin', False))
                login_user(user)
                flash("Login successful!", "success")
                return redirect(url_for('index'))
            else:
                flash("Incorrect password.", "error")
        else:
            flash("Username does not exist.", "error")

    return render_template('login.html', form=form)

# 登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@cache.cached(timeout=60)
def get_bitcoin_price():
    """获取实时比特币价格"""
    url = f'{BASE_URL}/api/v3/ticker/price'
    params = {'symbol': 'BTCUSDT'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    proxies = {"http": None, "https": None}

    try:
        response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = float(data['price'])
        return price
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve Bitcoin price: {e}")
        traceback.print_exc()
        return 0  # 修改此处以返回数字 0，避免返回字符串引发后续问题

# 新增一个独立的 get_historical_data 函数，并添加缓存
@cache.memoize(timeout=3600)  # 缓存 1 小时，可根据需要调整
def get_historical_data(symbol, interval, start_time, end_time_ms):
    """获取历史数据，并进行缓存"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    proxies = {"http": None, "https": None}
    all_data = []
    limit = 1000
    current_start_time = start_time

    while current_start_time < end_time_ms:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start_time,
            'endTime': end_time_ms,
            'limit': limit
        }
        try:
            response = requests.get(f'{BASE_URL}/api/v3/klines', params=params, headers=headers, proxies=proxies, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            all_data.extend(data)
            current_start_time = data[-1][0] + 1
        except requests.exceptions.RequestException as e:
            print("API request error:", e)
            traceback.print_exc()
            return []

    return all_data

@app.route('/')
def index():
    """主页显示所有日志和实时比特币价格"""
    try:
        logs = logs_collection.find()
        # 转换每个日志的 `_id` 为字符串，安全地处理缺失的 `user_id`
        logs = [{**log, "_id": str(log["_id"]), "user_id": str(log.get("user_id", ""))} for log in logs]
        bitcoin_price = get_bitcoin_price()
        return render_template('index.html', logs=logs, bitcoin_price=bitcoin_price)
    except Exception as e:
        print(f"Error loading index page: {e}")
        traceback.print_exc()
        flash("An error occurred while loading the main page.", "error")
        return redirect(url_for('login'))  # 或自定义错误页面

# 创建新日志（仅限登录用户）
@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if name and description:
            logs_collection.insert_one({
                'name': name,
                'description': description,
                'user_id': current_user.id  # 保存当前登录用户的ID
            })
            flash("Log created successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Name and Description are required.", "error")
            return render_template('create.html')
    return render_template('create.html')

@app.route('/edit/<log_id>', methods=['GET', 'POST'])
@login_required
def edit(log_id):
    try:
        log = logs_collection.find_one({'_id': ObjectId(log_id)})
        
        # 检查日志是否存在以及用户是否有权限
        if not log:
            flash("Log not found.", "error")
            return redirect(url_for('index'))
        
        # 确保 `user_id` 字段存在或安全地处理
        log_user_id = str(log.get('user_id', ""))

        # 只有当前用户是所有者或管理员才能编辑
        if log_user_id != current_user.id and not current_user.is_admin:
            flash("You do not have permission to edit this log.", "error")
            return redirect(url_for('index'))
        
        # 处理表单提交
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            if name and description:
                logs_collection.update_one(
                    {'_id': ObjectId(log_id)},
                    {'$set': {'name': name, 'description': description}}
                )
                flash("Log updated successfully!", "success")
                return redirect(url_for('index'))
            else:
                flash("Name and Description are required.", "error")
        
        # 渲染编辑页面
        return render_template('edit.html', log=log)
    
    except Exception as e:
        print(f"Error in edit function: {e}")
        traceback.print_exc()
        flash("An error occurred while editing the log.", "error")
        return redirect(url_for('index'))

# 在 delete 函数中增加安全的 user_id 检查
@app.route('/delete/<log_id>', methods=['POST'])
@login_required
def delete(log_id):
    log = logs_collection.find_one({'_id': ObjectId(log_id)})
    log_user_id = str(log.get('user_id', ""))  # 安全地获取 user_id
    
    # 增加检查
    if not log or (log_user_id != current_user.id and not current_user.is_admin):
        flash("You do not have permission to delete this log.", "error")
        return redirect(url_for('index'))

    logs_collection.delete_one({'_id': ObjectId(log_id)})
    flash("Log deleted successfully.", "success")
    return redirect(url_for('index'))

@app.route('/detail/<log_id>')
def detail(log_id):
    """显示日志详情"""
    log = logs_collection.find_one({'_id': ObjectId(log_id)})
    if not log:
        flash("Log not found", "error")
        return redirect(url_for('index'))
    return render_template('detail.html', log=log)

@app.route('/dca', methods=['GET', 'POST'])
def dca():
    """DCA 计算页面"""
    if request.method == 'POST':
        date_range = request.form.get('date_range', '').strip()
        interval = request.form.get('interval', '').strip()
        amount = request.form.get('amount', '').strip()

        session['last_date_range'] = date_range
        session['last_interval'] = interval
        session['last_amount'] = amount

        if not date_range or not interval or not amount:
            error = "All fields are required."
            return render_template('dca.html', error=error)

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError as ve:
            error = f"Invalid amount: {ve}"
            return render_template('dca.html', error=error)

        dates = date_range.split(' to ')
        if len(dates) == 2:
            start_date_str, end_date_str = dates
        else:
            error = "Please select a valid date range."
            return render_template('dca.html', error=error)

        try:
            total_invested, total_value, roi_percentage, investment_dates, investment_values = calculate_dca(
                start_date_str, end_date_str, interval, amount
            )
        except Exception as e:
            print(f"Error in calculate_dca: {e}")
            traceback.print_exc()
            error = "An error occurred during calculation. Please try again."
            return render_template('dca.html', error=error)

        return render_template('dca_result.html',
                               start_date=start_date_str,
                               end_date=end_date_str,
                               interval=interval,
                               amount=amount,
                               total_invested=total_invested,
                               total_value=total_value,
                               roi_percentage=roi_percentage,
                               investment_dates=investment_dates,
                               investment_values=investment_values)

    last_date_range = session.get('last_date_range', '')
    last_interval = session.get('last_interval', '')
    last_amount = session.get('last_amount', '')

    return render_template('dca.html', 
                           date_range=last_date_range, 
                           interval=last_interval, 
                           amount=last_amount)

# 在 calculate_dca 函数中，对 Binance API 请求进行缓存
def calculate_dca(start_date_str, end_date_str, interval, amount_per_interval):
    """计算定期定额投资回报"""
    symbol = 'BTCUSDT'
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError as e:
        print(f"Date parsing error: {e}")
        return 0, 0, 0, [], []

    if end_date < start_date:
        print("End date is before start date")
        return 0, 0, 0, [], []

    investment_dates = []
    current_date = start_date

    while current_date <= end_date:
        investment_dates.append(current_date)
        if interval == 'daily':
            current_date += datetime.timedelta(days=1)
        elif interval == 'weekly':
            current_date += datetime.timedelta(weeks=1)
        elif interval == 'monthly':
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(current_date.day, 28)
            try:
                current_date = current_date.replace(year=year, month=month, day=day)
            except ValueError as e:
                print(f"Date adjustment error: {e}")
                break
        else:
            print("Invalid interval")
            break

    total_invested = amount_per_interval * len(investment_dates)
    total_btc = 0.0
    investment_dates_formatted = []
    investment_values = []

    start_time = int(start_date.timestamp() * 1000)
    end_time_ms = int((end_date + datetime.timedelta(days=1)).timestamp() * 1000) - 1

    # 调用缓存的 get_historical_data 函数
    all_data = get_historical_data(symbol, '1d', start_time, end_time_ms)
    if not all_data:
        return 0, 0, 0, [], []

    date_price_map = {}
    for item in all_data:
        date = datetime.datetime.fromtimestamp(item[0] / 1000).date()
        closing_price = float(item[4])
        date_price_map[date] = closing_price

    for investment_date in investment_dates:
        price = date_price_map.get(investment_date.date())
        if price:
            btc_bought = amount_per_interval / price
            total_btc += btc_bought
            current_value = total_btc * price
            investment_dates_formatted.append(investment_date.strftime('%Y-%m-%d'))
            investment_values.append(round(current_value, 2))
        else:
            print(f"No data for date: {investment_date.strftime('%Y-%m-%d')}")
            investment_dates_formatted.append(investment_date.strftime('%Y-%m-%d'))
            investment_values.append(round(total_btc * price if price else 0, 2))

    current_price = get_bitcoin_price()
    if isinstance(current_price, str):
        current_price = 0.0
    total_value = total_btc * current_price
    roi_percentage = ((total_value - total_invested) / total_invested) * 100 if total_invested != 0 else 0

    return round(total_invested, 2), round(total_value, 2), round(roi_percentage, 2), investment_dates_formatted, investment_values

@app.route('/api/bitcoin-historical-data')
def bitcoin_historical_data():
    interval = request.args.get('interval', '1d')
    start_time = request.args.get('startTime')
    end_time = request.args.get('endTime')

    symbol = 'BTCUSDT'
    headers = {'User-Agent': 'Mozilla/5.0'}
    proxies = {"http": None, "https": None}

    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000
    }

    try:
        response = requests.get(f'{BASE_URL}/api/v3/klines', params=params, headers=headers, proxies=proxies, timeout=10)
        response.raise_for_status()
        data = response.json()
        prices = []
        for item in data:
            prices.append({
                'x': item[0],
                'o': float(item[1]),
                'h': float(item[2]),
                'l': float(item[3]),
                'c': float(item[4])
            })
        return jsonify({'prices': prices})
    except requests.exceptions.RequestException as e:
        print("API request error:", e)
        traceback.print_exc()
        return jsonify({'error': 'Unable to fetch data'}), 500

@app.route('/api/bitcoin-price')
def bitcoin_price_api():
    price = get_bitcoin_price()
    return jsonify({'price': price})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # 使用 Heroku 提供的端口
    app.run(host='0.0.0.0', port=port)
