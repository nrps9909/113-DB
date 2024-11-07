// 定義常量
const priceElement = document.getElementById('price');
const loadingElement = document.getElementById('loading');
const ctx = document.getElementById('klineChart').getContext('2d');
const rangeButtons = document.querySelectorAll('.range-btn');
const customRangePicker = document.getElementById('custom-range-picker');
const fetchCustomDataButton = document.getElementById('fetch-custom-data');

// 更新價格顯示樣式
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
setInterval(fetchBitcoinPrice, 10000); // 每秒更新价格

// 初始化 K 线图
Chart.defaults.color = '#e0e0e0';
Chart.defaults.font.family = 'Orbitron, sans-serif';

let klineChart = new Chart(ctx, {
    type: 'candlestick',
    data: {
        datasets: [{
            label: 'Bitcoin Price',
            data: [],
            color: {
                up: '#00ff00',      
                down: '#ff0000',    
                unchanged: '#e0e0e0' 
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

// 获取并更新图表数据
function fetchData(range, startDate = null, endDate = null) {
    const intervalMapping = {
        '1d': '3m',
        '7d': '15m',
        '1mo': '1h',
        '1y': '12h',
        '3y': '3d',
        '10y': '1w'
    };
    let interval = intervalMapping[range] || '3m';
    let startTime;
    let endTime = Date.now();

    if (range === 'custom') {
        if (!startDate || !endDate) {
            alert("Please select start and end dates.");
            return;
        }
        startTime = startDate.getTime();
        endTime = endDate.getTime();
        interval = determineInterval(startTime, endTime);
    } else {
        const dayMs = 24 * 60 * 60 * 1000;
        const rangeMs = {
            '1d': 1 * dayMs,
            '7d': 7 * dayMs,
            '1mo': 30 * dayMs,
            '1y': 365 * dayMs,
            '3y': 3 * 365 * dayMs,
            '10y': endTime - new Date('2017-01-01').getTime()
        };
        startTime = endTime - (rangeMs[range] || dayMs);
    }

    loadingElement.style.display = 'block';
    $.ajax({
        url: '/api/bitcoin-historical-data',
        data: { interval: interval, startTime: startTime, endTime: endTime },
        success: function(data) {
            if (data.error) {
                alert("Error fetching data: " + data.error);
                loadingElement.style.display = 'none';
                return;
            }
            updateChart(data.prices);
            loadingElement.style.display = 'none';
        },
        error: function(error) {
            console.error("Unable to fetch data", error);
            loadingElement.style.display = 'none';
            alert("Unable to fetch data. Please try again later.");
        }
    });
}

// 更新图表数据
function updateChart(prices) {
    const chartData = prices.map(item => ({
        x: item.x,
        o: item.o,
        h: item.h,
        l: item.l,
        c: item.c
    }));

    klineChart.data.datasets[0].data = chartData;
    klineChart.resetZoom();

    if (chartData.length > 0) {
        klineChart.options.scales.x.min = chartData[0].x;
        klineChart.options.scales.x.max = chartData[chartData.length - 1].x;

        const yValues = chartData.flatMap(d => [d.o, d.h, d.l, d.c]);
        klineChart.options.scales.y.min = Math.min(...yValues);
        klineChart.options.scales.y.max = Math.max(...yValues);

        klineChart.options.plugins.zoom.limits = {
            x: { min: chartData[0].x, max: chartData[chartData.length - 1].x },
            y: { min: Math.min(...yValues), max: Math.max(...yValues) }
        };
    }

    klineChart.update();
}

// 确定合适的时间间隔
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
rangeButtons.forEach(button => {
    button.addEventListener('click', () => {
        const range = button.getAttribute('data-range');
        if (range === 'custom') {
            customRangePicker.style.display = 'block';
        } else {
            customRangePicker.style.display = 'none';
            fetchData(range);
        }
    });
});

// 处理自定义日期范围的请求
fetchCustomDataButton.addEventListener('click', () => {
    if (!startDate || !endDate) {
        alert("Please select start and end dates.");
        return;
    }
    fetchData('custom', startDate, endDate);
});

// 初次加载图表
fetchData('1d');
