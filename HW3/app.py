from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests
import traceback
import datetime
import os
from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # 從環境變數中讀取密鑰

# 從環境變數中獲取 MongoDB Atlas 的 URI
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

# 指定要使用的資料庫和集合
db = client['my_database']  # 替換成你的資料庫名稱
collection = db['startup_log']  # 替換成你要使用的集合名稱

# Binance API URL
BASE_URL = 'https://data-api.binance.vision'

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
        return "Unable to retrieve price"

@app.route('/')
def index():
    """主页，显示所有日志和实时比特币价格"""
    logs = collection.find()
    bitcoin_price = get_bitcoin_price()
    return render_template('index.html', logs=logs, bitcoin_price=bitcoin_price)

@app.route('/create', methods=['GET', 'POST'])
def create():
    """创建新日志"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if name and description:
            # 安全地插入資料
            collection.insert_one({'name': name, 'description': description})
            return redirect(url_for('index'))
        else:
            error = "Name and Description are required."
            return render_template('create.html', error=error)
    return render_template('create.html')

@app.route('/edit/<log_id>', methods=['GET', 'POST'])
def edit(log_id):
    """编辑日志"""
    log = collection.find_one({'_id': ObjectId(log_id)})
    if not log:
        return "Log not found", 404
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if name and description:
            # 安全地更新資料
            collection.update_one({'_id': ObjectId(log_id)}, {'$set': {'name': name, 'description': description}})
            return redirect(url_for('index'))
        else:
            error = "Name and Description are required."
            return render_template('edit.html', log=log, error=error)
    return render_template('edit.html', log=log)

@app.route('/delete/<log_id>', methods=['POST'])
def delete(log_id):
    """删除日志"""
    result = collection.delete_one({'_id': ObjectId(log_id)})
    if result.deleted_count == 1:
        return redirect(url_for('index'))
    else:
        return "Log not found", 404

@app.route('/detail/<log_id>')
def detail(log_id):
    """显示日志详情"""
    log = collection.find_one({'_id': ObjectId(log_id)})
    if not log:
        return "Log not found", 404
    return render_template('detail.html', log=log)

@app.route('/dca', methods=['GET', 'POST'])
def dca():
    """DCA 计算页面"""
    if request.method == 'POST':
        # 获取用户输入的数据
        date_range = request.form.get('date_range', '').strip()
        interval = request.form.get('interval', '').strip()
        amount = request.form.get('amount', '').strip()

        # 保存用户的输入到 session 中
        session['last_date_range'] = date_range
        session['last_interval'] = interval
        session['last_amount'] = amount

        if not date_range or not interval or not amount:
            error = "所有字段都是必填的。"
            return render_template('dca.html', error=error)

        # 檢查並轉換投資金額
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError as ve:
            error = f"Invalid amount: {ve}"
            return render_template('dca.html', error=error)

        # 解析日期范围
        dates = date_range.split(' to ')
        if len(dates) == 2:
            start_date_str, end_date_str = dates
        else:
            error = "Please select a valid date range."
            return render_template('dca.html', error=error)

        # 調用計算函數
        total_invested, total_value, roi_percentage, investment_dates, investment_values = calculate_dca(
            start_date_str, end_date_str, interval, amount
        )

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

    # 在 GET 請求時，從 session 中讀取上次的輸入，並傳遞給模板
    last_date_range = session.get('last_date_range', '')
    last_interval = session.get('last_interval', '')
    last_amount = session.get('last_amount', '')

    return render_template('dca.html', 
                           date_range=last_date_range, 
                           interval=last_interval, 
                           amount=last_amount)

def calculate_dca(start_date_str, end_date_str, interval, amount_per_interval):
    """计算定期定额投资回报"""
    symbol = 'BTCUSDT'

    # 转换日期字符串为 datetime 对象
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError as e:
        print(f"Date parsing error: {e}")
        return 0, 0, 0, [], []

    # 确保结束日期不早于开始日期
    if end_date < start_date:
        print("End date is before start date")
        return 0, 0, 0, [], []

    # 根据间隔生成投资日期列表
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

    headers = {'User-Agent': 'Mozilla/5.0'}
    proxies = {"http": None, "https": None}

    # 批量获取价格数据
    all_data = []
    limit = 1000
    start_time = int(start_date.timestamp() * 1000)
    end_time_ms = int((end_date + datetime.timedelta(days=1)).timestamp() * 1000) - 1
    current_start_time = start_time

    while current_start_time < end_time_ms:
        params = {
            'symbol': symbol,
            'interval': '1d',
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
            return 0, 0, 0, [], []

    # 创建日期到收盘价的映射
    date_price_map = {}
    for item in all_data:
        date = datetime.datetime.fromtimestamp(item[0] / 1000).date()
        closing_price = float(item[4])
        date_price_map[date] = closing_price

    # 计算每次投资购买的 BTC 数量，并记录投资价值
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

# API 端点，用于获取历史数据
@app.route('/api/bitcoin-historical-data')
def bitcoin_historical_data():
    """获取比特币历史数据的 API 端点"""
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

# API 端点，用于获取实时比特币价格
@app.route('/api/bitcoin-price')
def bitcoin_price_api():
    """获取实时比特币价格的 API 端点"""
    price = get_bitcoin_price()
    return jsonify({'price': price})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
    