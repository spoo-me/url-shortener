// Statistics Dashboard JavaScript - Using new /api/v1/stats endpoint
class StatisticsDashboard {
    constructor() {
        this.charts = new Map();
        this.currentTimeRange = '7d';
        this.startDate = null;
        this.endDate = null;
        this.refreshInterval = null;
        this.apiData = null;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDashboardData();
        this.setupAutoRefresh();
    }

    setupEventListeners() {
        // Time range selector
        document.getElementById('timeRange').addEventListener('change', (e) => {
            this.currentTimeRange = e.target.value;
            if (e.target.value === 'custom') {
                this.showDateRangeModal();
            } else {
                this.startDate = null;
                this.endDate = null;
                this.loadDashboardData();
            }
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadDashboardData();
        });

        // Modal events
        document.getElementById('closeModal').addEventListener('click', () => {
            this.hideDateRangeModal();
        });

        document.getElementById('cancelRange').addEventListener('click', () => {
            this.hideDateRangeModal();
            document.getElementById('timeRange').value = '7d';
            this.currentTimeRange = '7d';
        });

        document.getElementById('applyRange').addEventListener('click', () => {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            if (startDate && endDate) {
                this.startDate = startDate;
                this.endDate = endDate;
                this.hideDateRangeModal();
                this.loadDashboardData();
            }
        });

        // Close modal on backdrop click
        document.getElementById('dateRangeModal').addEventListener('click', (e) => {
            if (e.target.id === 'dateRangeModal') {
                this.hideDateRangeModal();
            }
        });
    }

    showDateRangeModal() {
        document.getElementById('dateRangeModal').style.display = 'flex';
    }

    hideDateRangeModal() {
        document.getElementById('dateRangeModal').style.display = 'none';
    }

    async loadDashboardData() {
        try {
            const params = new URLSearchParams({
                scope: 'all',
                group_by: 'time,browser,os,country,referrer,device,key',
                metrics: 'clicks,unique_clicks'
            });

            // Add time range parameters based on selection
            if (this.startDate && this.endDate) {
                params.append('start_date', this.startDate);
                params.append('end_date', this.endDate);
            } else {
                // Convert dashboard time range to API format
                const rangeMap = {
                    '7d': '7d',
                    '30d': '30d',
                    '90d': '90d',
                    '1y': '365d'
                };
                params.append('range', rangeMap[this.currentTimeRange] || '7d');
            }

            const response = await fetch(`/api/v1/stats?${params.toString()}`, {
                method: 'GET',
                credentials: 'include', // Include cookies for authentication
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            this.apiData = await response.json();
            console.log('API Response:', this.apiData); // Debug log
            this.updateDashboard(this.apiData);

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data. Please try again.');
        }
    }

    updateDashboard(data) {
        this.updateStatCards(data);
        this.updateCharts(data);
    }

    updateStatCards(data) {
        // Get total metrics from summary
        const totalClicks = data.summary?.total_clicks || 0;
        const uniqueClicks = data.summary?.unique_clicks || 0;
        const uniqueRate = totalClicks > 0 ? ((uniqueClicks / totalClicks) * 100).toFixed(1) : 0;
        const activeUrls = data.summary?.total_urls || 0;

        // Update stat values
        document.getElementById('totalClicks').textContent = this.formatNumber(totalClicks);
        document.getElementById('uniqueClicks').textContent = this.formatNumber(uniqueClicks);
        document.getElementById('clickRate').textContent = `${uniqueRate}%`;
        document.getElementById('activeUrls').textContent = this.formatNumber(activeUrls);
    }

    updateChangeIndicator(elementId, changeValue) {
        const element = document.getElementById(elementId);
        const isPositive = changeValue > 0;
        const isNegative = changeValue < 0;

        element.textContent = `${isPositive ? '+' : ''}${changeValue}${elementId.includes('Rate') ? '%' : ''}`;
        element.className = `stat-change ${isPositive ? 'positive' : isNegative ? 'negative' : 'neutral'}`;
    }

    updateCharts(data) {
        this.updateTimeSeriesChart(data);
        this.updateKeyChart(data);
        this.updateDeviceChart(data);
        this.updateBrowserChart(data);
        this.updateOsChart(data);
        this.updateReferrerChart(data);
        this.updateCountryChart(data);
    }

    updateTimeSeriesChart(data) {
        const canvas = document.getElementById('timeSeriesChart');
        const ctx = canvas.getContext('2d');

        // Destroy existing chart
        if (this.charts.has('timeSeries')) {
            this.charts.get('timeSeries').destroy();
        }

        // Extract time series data from metrics
        const clicksByTime = data.metrics?.clicks_by_time || [];
        const uniqueClicksByTime = data.metrics?.unique_clicks_by_time || [];

        // Convert to chart format
        const labels = clicksByTime.map(item => item.time || item.date);
        const clicksData = clicksByTime.map(item => item.clicks || item.value);
        const uniqueClicksData = uniqueClicksByTime.map(item => item.unique_clicks || item.value);

        const datasets = [];
        const dataOption = document.getElementById('counterDataOption')?.value || 'compare';

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Total Clicks',
                data: clicksData,
                fill: 'start',
                backgroundColor: 'rgba(255, 159, 64, 0.15)',
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 2,
                tension: 0.3,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Clicks',
                data: uniqueClicksData,
                fill: 'start',
                backgroundColor: 'rgba(201, 203, 207, 0.25)',
                borderColor: 'rgba(201, 203, 207, 1)',
                borderWidth: 2,
                tension: 0.3,
            });
        }

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff' },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff'
                    }
                },
            },
        });

        this.charts.set('timeSeries', chart);
    }

    updateBrowserChart(data) {
        const canvas = document.getElementById('browserChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('browser')) {
            this.charts.get('browser').destroy();
        }

        // Extract browser data from metrics
        const clicksByBrowser = data.metrics?.clicks_by_browser || [];
        const uniqueClicksByBrowser = data.metrics?.unique_clicks_by_browser || [];

        // Convert to chart format
        const browserLabels = clicksByBrowser.map(item => item.browser);
        const browserClicks = clicksByBrowser.map(item => item.clicks);
        const browserUniqueClicks = uniqueClicksByBrowser.map(item => item.unique_clicks);

        const dataOption = document.getElementById('browserDataOption')?.value || 'compare';
        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Browsers',
                data: browserClicks,
                backgroundColor: 'rgba(153, 102, 255, 0.15)',
                borderColor: 'rgba(153, 102, 255, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Browsers',
                data: browserUniqueClicks,
                backgroundColor: 'rgba(255, 159, 64, 0.25)',
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: browserLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: { labels: { color: '#fff' } },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff'
                    }
                },
            },
        });

        this.charts.set('browser', chart);
    }

    updateOsChart(data) {
        const canvas = document.getElementById('osChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('os')) {
            this.charts.get('os').destroy();
        }

        // Extract OS data from metrics
        const clicksByOs = data.metrics?.clicks_by_os || [];
        const uniqueClicksByOs = data.metrics?.unique_clicks_by_os || [];

        // Convert to chart format
        const osLabels = clicksByOs.map(item => item.os);
        const osClicks = clicksByOs.map(item => item.clicks);
        const osUniqueClicks = uniqueClicksByOs.map(item => item.unique_clicks);

        const dataOption = document.getElementById('osDataOption')?.value || 'compare';
        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Platforms',
                data: osClicks,
                backgroundColor: 'rgba(144, 238, 144, 0.15)',
                borderColor: 'rgba(144, 238, 144, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Platforms',
                data: osUniqueClicks,
                backgroundColor: 'rgba(255, 69, 0, 0.25)',
                borderColor: 'rgba(255, 69, 0, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: osLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: { labels: { color: '#fff' } },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff'
                    }
                },
            },
        });

        this.charts.set('os', chart);
    }

    updateReferrerChart(data) {
        const canvas = document.getElementById('referrerChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('referrer')) {
            this.charts.get('referrer').destroy();
        }

        // Extract referrer data from metrics
        const clicksByReferrer = data.metrics?.clicks_by_referrer || [];
        const uniqueClicksByReferrer = data.metrics?.unique_clicks_by_referrer || [];

        // Convert to chart format
        const referrerLabels = clicksByReferrer.map(item => item.referrer);
        const referrerClicks = clicksByReferrer.map(item => item.clicks);
        const referrerUniqueClicks = uniqueClicksByReferrer.map(item => item.unique_clicks);

        const dataOption = document.getElementById('referrerDataOption')?.value || 'compare';
        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Referrers',
                data: referrerClicks,
                backgroundColor: 'rgba(128, 0, 128, 0.15)',
                borderColor: 'rgba(128, 0, 128, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Referrers',
                data: referrerUniqueClicks,
                backgroundColor: 'rgba(255, 0, 255, 0.25)',
                borderColor: 'rgba(255, 0, 255, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: referrerLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: { labels: { color: '#fff' } },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff'
                    }
                },
            },
        });

        this.charts.set('referrer', chart);
    }

    updateCountryChart(data) {
        const countryChartContainer = document.getElementById('countryChart');
        countryChartContainer.innerHTML = ''; // Clear previous map

        document.getElementById('country-container').style.padding = "5px";

        // Extract country data from metrics
        const clicksByCountry = data.metrics?.clicks_by_country || [];
        const uniqueClicksByCountry = data.metrics?.unique_clicks_by_country || [];

        const dataOption = document.getElementById('countryDataOption')?.value || 'total';
        const countryData = dataOption === 'unique' ? uniqueClicksByCountry : clicksByCountry;

        // Convert to AnyChart format: array of {id: 'country_code', value: clicks}
        const mapData = countryData.map(item => ({
            id: item.country, // Assuming country codes are provided
            value: item.clicks || item.unique_clicks
        }));

        const mapTitle = dataOption === 'total' ? "Countries Clicks Heatmap" : "Countries Unique Clicks Heatmap";

        // Create AnyChart map
        var dataSet = anychart.data.set(mapData);
        var map = anychart.map();

        map.geoData("anychart.maps.world");

        var series = map.choropleth(dataSet);

        series.colorScale(
            anychart.scales.linearColor("#f5e6f7", "#ba68c8", "#9c27b0", "#6a1b9a")
        );

        series.stroke('#9c27b0', 1, '5 2', 'round');

        series.hovered().fill(function (d) {
            return anychart.color.darken(d.sourceColor, 0.1);
        });

        series.tooltip().format(function(e){
            return "Clicks: <b>" + e.getData("value") + "</b>";
        });

        var title = map.title();
        title.enabled(true);
        title.text(mapTitle);
        title.fontColor("#ffffff");
        title.fontSize(12);
        title.padding(0, 0, 10, 0);

        map.tooltip().useHtml(true);

        map.colorRange().enabled(true);
        map.colorRange().orientation('bottom');
        map.colorRange().labels({ 'fontSize': 13, 'fontColor': 'white' });
        map.colorRange().stroke('');

        var grids = map.grids();
        grids.enabled(true);
        grids.stroke("#ffffff", 0.3, "5 2", "round");

        var marker = map.colorRange().marker();
        marker.size(7);

        map.interactivity().zoomOnMouseWheel(true);
        map.interactivity().keyboardZoomAndMove(true);
        map.interactivity().zoomOnDoubleClick(true);

        var zoomController = anychart.ui.zoom();
        zoomController.target(map);
        zoomController.render();

        map.container("countryChart");
        map.contextMenu(true);

        map.background().fill("rgba(255, 255, 255, 0)");

        map.contextMenu().itemsFormatter(function (items) {
            delete items["full-screen-separator"];
            delete items["about"];
            delete items["share-with"];
            delete items["print-chart"];
            return items;
        });

        map.draw();

        // Store map instance for cleanup
        this.charts.set('country', map);
    }

    updateDeviceChart(data) {
        const canvas = document.getElementById('deviceChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('device')) {
            this.charts.get('device').destroy();
        }

        // Extract device data from metrics
        const clicksByDevice = data.metrics?.clicks_by_device || [];
        const uniqueClicksByDevice = data.metrics?.unique_clicks_by_device || [];

        // Convert to chart format
        const deviceLabels = clicksByDevice.map(item => item.device);
        const deviceClicks = clicksByDevice.map(item => item.clicks);
        const deviceUniqueClicks = uniqueClicksByDevice.map(item => item.unique_clicks);

        const dataOption = document.getElementById('deviceDataOption')?.value || 'compare';
        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Devices',
                data: deviceClicks,
                backgroundColor: 'rgba(75, 192, 192, 0.15)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Devices',
                data: deviceUniqueClicks,
                backgroundColor: 'rgba(255, 99, 132, 0.25)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: deviceLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: { labels: { color: '#fff' } },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff'
                    }
                },
            },
        });

        this.charts.set('device', chart);
    }

    updateKeyChart(data) {
        const canvas = document.getElementById('keyChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('key')) {
            this.charts.get('key').destroy();
        }

        // Extract key data from metrics
        const clicksByKey = data.metrics?.clicks_by_key || [];
        const uniqueClicksByKey = data.metrics?.unique_clicks_by_key || [];

        const dataOption = document.getElementById('keyDataOption')?.value || 'total';
        const keyData = dataOption === 'unique' ? uniqueClicksByKey : clicksByKey;

        // Convert to chart format and take top 10
        const topKeys = keyData.slice(0, 10);
        const keyLabels = topKeys.map(item => item.key);
        const keyValues = topKeys.map(item => item.clicks || item.unique_clicks);

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: keyLabels,
                datasets: [{
                    label: dataOption === 'unique' ? 'Unique Clicks per URL' : 'Total Clicks per URL',
                    data: keyValues,
                    backgroundColor: 'rgba(255, 193, 7, 0.6)',
                    borderColor: 'rgba(255, 193, 7, 1)',
                    borderWidth: 2,
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        title: {
                            display: true,
                            text: 'Clicks',
                            color: '#fff'
                        }
                    },
                    y: {
                        ticks: {
                            color: '#fff',
                            maxTicksLimit: 10
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        callbacks: {
                            afterBody: function(context) {
                                const index = context[0].dataIndex;
                                const item = topKeys[index];
                                if (item.clicks_percentage) {
                                    return `${item.clicks_percentage.toFixed(1)}% of total clicks`;
                                }
                                return '';
                            }
                        }
                    }
                },
            },
        });

        this.charts.set('key', chart);
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    setupAutoRefresh() {
        // Refresh every 5 minutes
        this.refreshInterval = setInterval(() => {
            this.loadDashboardData();
        }, 5 * 60 * 1000);
    }

    showError(message) {
        console.error(message);
        // You can implement a toast notification here
        alert(message); // Simple fallback
    }

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        this.charts.forEach(chart => {
            if (chart.destroy) {
                chart.destroy();
            } else if (chart.dispose) {
                chart.dispose(); // For AnyChart maps
            }
        });
        this.charts.clear();
    }
}

// Global functions for toggle view functionality (matching original stats-view)
function toggleView(chartType) {
    const chartElement = chartType === 'country' ?
        document.getElementById(`${chartType}Chart`) :
        document.getElementById(`${chartType}Chart`);
    const jsonPre = document.querySelector(`.${chartType}JsonPre`);
    const jsonDataElement = document.getElementById(`${chartType}Json`);

    if (!chartElement || !jsonPre || !jsonDataElement) return;

    if (chartElement.style.display === 'none') {
        chartElement.style.display = 'block';
        jsonPre.style.display = 'none';
        jsonDataElement.style.display = 'none';

        if (chartType === 'country') {
            document.getElementById("country-container").style.padding = "5px";
        }
    } else {
        chartElement.style.display = 'none';
        jsonPre.style.display = 'block';
        jsonDataElement.style.display = 'block';

        // Show the current API data
        if (window.dashboard && window.dashboard.apiData) {
            jsonDataElement.textContent = JSON.stringify(window.dashboard.apiData, null, 2);
        }

        if (chartType === 'country') {
            document.getElementById("country-container").style.padding = "20px";
        }
    }
}

// Update chart functions for when selectors change
function updateTimeSeriesChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateTimeSeriesChart(window.dashboard.apiData);
    }
}

function updateBrowserChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateBrowserChart(window.dashboard.apiData);
    }
}

function updateOsChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateOsChart(window.dashboard.apiData);
    }
}

function updateReferrerChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateReferrerChart(window.dashboard.apiData);
    }
}

function updateCountryChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateCountryChart(window.dashboard.apiData);
    }
}

function updateDeviceChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateDeviceChart(window.dashboard.apiData);
    }
}

function updateKeyChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateKeyChart(window.dashboard.apiData);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new StatisticsDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.destroy();
    }
});