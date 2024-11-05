// main.js

// 获取实时价格元素
const priceElement = document.getElementById('price');

// 更新价格显示样式
function updatePrice(newPrice) {
    const currentPrice = parseFloat(priceElement.textContent.replace('$', '')) || 0;
    priceElement.textContent = `$${newPrice.toFixed(2)}`;

    if (newPrice > currentPrice) {
        priceElement.classList.add('price-up');
        priceElement.classList.remove('price-down');
    } else if (newPrice < currentPrice) {
        priceElement.classList.add('price-down');
        priceElement.classList.remove('price-up');
    }

    setTimeout(() => {
        priceElement.classList.remove('price-up', 'price-down');
    }, 500);
}

// 获取实时比特币价格并更新页面
function fetchBitcoinPrice() {
    $.ajax({
        url: '/api/bitcoin-price',
        success: function(data) {
            const newPrice = parseFloat(data.price);
            if (!isNaN(newPrice)) {
                updatePrice(newPrice);
            }
        },
        error: function(error) {
            console.error("Unable to fetch Bitcoin price", error);
        }
    });
}

// 初次获取价格
fetchBitcoinPrice();

// 每秒更新价格
setInterval(fetchBitcoinPrice, 10000);

// 初始化 K 线图
const ctx = document.getElementById('klineChart').getContext('2d');

// 设置全局默认选项
Chart.defaults.color = '#e0e0e0';
Chart.defaults.font.family = 'Orbitron, sans-serif';

// 定义 K 线图
let klineChart = new Chart(ctx, {
    type: 'candlestick',
    data: {
        datasets: [{
            label: 'Bitcoin Price',
            data: [],
            color: {
                up: '#00ff00',      // 霓虹绿色
                down: '#ff0000',    // 霓虹红色
                unchanged: '#e0e0e0' // 淡灰色
            }
        }]
    },
    options: {
        responsive: true,
        scales: {
            x: {
                type: 'time',
                grid: { color: '#333' },
                time: { tooltipFormat: 'MMM dd, yyyy HH:mm' },
                ticks: { color: '#e0e0e0' },
                title: { display: true, text: 'Time', color: '#e0e0e0' }
            },
            y: {
                grid: { color: '#333' },
                ticks: { color: '#e0e0e0' },
                title: { display: true, text: 'Price (USD)', color: '#e0e0e0' }
            }
        },
        plugins: {
            legend: { labels: { color: '#e0e0e0' } },
            zoom: {
                pan: { enabled: true, mode: 'x' },
                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                limits: { x: { min: null, max: null }, y: { min: null, max: null } }
            }
        }
    }
});

// 根据选择的范围获取数据并更新图表
function fetchData(range, startDate = null, endDate = null) {
    let interval;
    let startTime;
    let endTime = Date.now(); // 使用 let 以便重新赋值

    if (range === 'custom') {
        if (!startDate || !endDate) {
            alert("Please select start and end dates.");
            return;
        }
        startTime = startDate.getTime();
        endTime = endDate.getTime(); // 允许赋值
        interval = determineInterval(startTime, endTime);
    } else {
        switch (range) {
            case '1d':
                interval = '3m';
                startTime = endTime - 1 * 24 * 60 * 60 * 1000;
                break;
            case '7d':
                interval = '15m';
                startTime = endTime - 7 * 24 * 60 * 60 * 1000;
                break;
            case '1mo':
                interval = '1h';
                startTime = endTime - 30 * 24 * 60 * 60 * 1000;
                break;
            case '1y':
                interval = '12h';
                startTime = endTime - 365 * 24 * 60 * 60 * 1000;
                break;
            case '3y':
                interval = '3d';
                startTime = endTime - 3 * 365 * 24 * 60 * 60 * 1000;
                break;
            case '10y':
                interval = '1w';
                startTime = new Date('2017-01-01').getTime();
                break;
            default:
                interval = '3m';
                startTime = endTime - 1 * 24 * 60 * 60 * 1000;
        }
    }

    $('#loading').show();
    $.ajax({
        url: '/api/bitcoin-historical-data',
        data: { interval: interval, startTime: startTime, endTime: endTime },
        success: function(data) {
            if (data.error) {
                alert("Error fetching data: " + data.error);
                $('#loading').hide();
                return;
            }

            const chartData = data.prices.map(item => ({
                x: item.x,
                o: item.o,
                h: item.h,
                l: item.l,
                c: item.c
            }));

            // 更新 K 线图数据
            klineChart.data.datasets[0].data = chartData;
            klineChart.resetZoom();

            // 设置默认 x 轴和 y 轴范围
            if (chartData.length > 0) {
                klineChart.options.scales.x.min = chartData[0].x;
                klineChart.options.scales.x.max = chartData[chartData.length - 1].x;

                const yValues = chartData.flatMap(d => [d.o, d.h, d.l, d.c]);
                klineChart.options.scales.y.min = Math.min(...yValues);
                klineChart.options.scales.y.max = Math.max(...yValues);

                // 设置缩放和平移限制
                klineChart.options.plugins.zoom.limits = {
                    x: { min: chartData[0].x, max: chartData[chartData.length - 1].x },
                    y: { min: Math.min(...yValues), max: Math.max(...yValues) }
                };
            }

            // 更新图表
            klineChart.update();

            $('#loading').hide();
        },
        error: function(error) {
            console.error("Unable to fetch data", error);
            $('#loading').hide();
            alert("Unable to fetch data. Please try again later.");
        }
    });
}

// 根据日期范围决定合适的间隔
function determineInterval(startTime, endTime) {
    const diff = endTime - startTime;
    const day = 24 * 60 * 60 * 1000;
    if (diff <= 7 * day) return '15m';
    else if (diff <= 30 * day) return '1h';
    else if (diff <= 365 * day) return '12h';
    else return '1d';
}

// 初始化 Flatpickr
let startDate = null;
let endDate = null;

flatpickr("#date-range", {
    mode: "range",
    dateFormat: "Y-m-d",
    maxDate: "today",
    onChange: function(selectedDates) {
        if (selectedDates.length === 2) {
            startDate = selectedDates[0];
            endDate = selectedDates[1];
        }
    }
});

// 为每个范围按钮添加点击事件
document.querySelectorAll('.range-btn').forEach(button => {
    button.addEventListener('click', () => {
        const range = button.getAttribute('data-range');
        if (range === 'custom') {
            document.getElementById('custom-range-picker').style.display = 'block';
        } else {
            document.getElementById('custom-range-picker').style.display = 'none';
            fetchData(range);
        }
    });
});

// 处理自定义日期范围的请求
document.getElementById('fetch-custom-data').addEventListener('click', () => {
    if (!startDate || !endDate) {
        alert("Please select start and end dates.");
        return;
    }
    fetchData('custom', startDate, endDate);
});

// 初次加载图表
fetchData('1d');
