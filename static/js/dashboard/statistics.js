// Statistics Dashboard JavaScript - Using new /api/v1/stats endpoint
class StatisticsDashboard {
    constructor() {
        this.charts = new Map();
        this.currentTimeRange = null;
        this.startDate = null;
        this.endDate = null;
        this.refreshInterval = null;
        this.autoRefreshInterval = null;
        this.apiData = null;
        this.dateRangePicker = null;

        this.init();
    }

    init() {
        this.setupDateRangePicker();
        this.setupEventListeners();
        this.loadDashboardData();
        this.setupAutoRefresh();
        this.restoreAutoRefreshSetting();
    }

    setupDateRangePicker() {
        this.dateRangePicker = new DateRangePicker({
            container: 'dateRangeContainer',
            onRangeChange: (dateRange) => {
                this.handleDateRangeChange(dateRange);
            },
            defaultRange: 'last-7-days'
        });
    }

    handleDateRangeChange(dateRange) {
        console.log('Date range changed:', dateRange);

        // Convert the date range to API parameters
        this.startDate = dateRange.start;
        this.endDate = dateRange.end;
        this.currentTimeRange = dateRange.range;

        // Reload dashboard data with new range
        this.loadDashboardData();
    }

    setupEventListeners() {
        // Manual refresh button click
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadDashboardData();
            });
        }

        // Auto-refresh dropdown toggle
        const autoRefreshBtn = document.querySelector('.auto-refresh-btn');
        if (autoRefreshBtn) {
            autoRefreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const dropdown = autoRefreshBtn.nextElementSibling;
                if (dropdown && dropdown.classList.contains('dropdown-menu')) {
                    dropdown.classList.toggle('show');
                }
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const autoRefreshDropdown = e.target.closest('.auto-refresh-dropdown');
            if (!autoRefreshDropdown) {
                const openDropdowns = document.querySelectorAll('.auto-refresh-dropdown .dropdown-menu.show');
                openDropdowns.forEach(dropdown => dropdown.classList.remove('show'));
            }
        });

        // Table view button controls
        this.setupTableViewControls();

        // Cascade button controls
        this.setupCascadeControls();
    }

    setupCascadeControls() {
        // Handle cascade button clicks
        document.querySelectorAll('.cascade-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Don't proceed if button is disabled
                if (btn.disabled) {
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }

                e.stopPropagation();
                const dropdown = btn.nextElementSibling;

                // Close other dropdowns
                document.querySelectorAll('.cascade-dropdown').forEach(dd => {
                    if (dd !== dropdown) dd.classList.remove('show');
                });

                // Toggle current dropdown
                dropdown.classList.toggle('show');
            });
        });

        // Handle cascade option selection
        document.querySelectorAll('.cascade-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const cascadeSelect = option.closest('.cascade-select');
                
                // Don't proceed if cascade select is disabled
                if (cascadeSelect && cascadeSelect.style.pointerEvents === 'none') {
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }

                const value = option.dataset.value;
                const chartType = cascadeSelect.dataset.chart;

                // Update active states
                cascadeSelect.querySelectorAll('.cascade-option').forEach(opt => {
                    opt.classList.remove('active');
                });
                option.classList.add('active');

                // Update main button
                const mainBtn = cascadeSelect.querySelector('.cascade-btn');
                mainBtn.dataset.value = value;
                mainBtn.querySelector('i').className = option.querySelector('i').className;
                mainBtn.title = option.querySelector('span').textContent;

                // Close dropdown
                cascadeSelect.querySelector('.cascade-dropdown').classList.remove('show');

                // Update chart
                this.updateChartByType(chartType, value);
            });
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', () => {
            document.querySelectorAll('.cascade-dropdown').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        });
    }

    setupTableViewControls() {
        // Handle table view button clicks
        document.querySelectorAll('.table-view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const chartType = btn.dataset.chart;
                this.toggleTableView(chartType, btn);
            });
        });
    }

    toggleTableView(chartType, btn) {
        const chartContainer = document.getElementById(chartType);
        const tableContainer = document.getElementById(chartType.replace('Chart', 'Table'));
        const cascadeSelect = document.querySelector(`[data-chart="${chartType}"].cascade-select`);

        if (!chartContainer || !tableContainer) return;

        const isTableVisible = tableContainer.style.display !== 'none';

        if (isTableVisible) {
            // Switch to chart view with fade transition
            this.fadeTransition(tableContainer, chartContainer, () => {
                btn.classList.remove('active');
                btn.title = 'Table View';

                // Enable cascade selector
                if (cascadeSelect) {
                    cascadeSelect.style.pointerEvents = 'auto';
                    cascadeSelect.style.opacity = '1';
                    const cascadeBtn = cascadeSelect.querySelector('.cascade-btn');
                    if (cascadeBtn) {
                        cascadeBtn.disabled = false;
                    }
                }

                // Special handling for country chart (AnyChart map)
                if (chartType === 'countryChart') {
                    document.getElementById("country-container").style.padding = "5px";
                }
            });
        } else {
            // Switch to table view with fade transition
            this.fadeTransition(chartContainer, tableContainer, () => {
                btn.classList.add('active');
                btn.title = 'Chart View';

                // Disable cascade selector
                if (cascadeSelect) {
                    cascadeSelect.style.pointerEvents = 'none';
                    cascadeSelect.style.opacity = '0.5';
                    const cascadeBtn = cascadeSelect.querySelector('.cascade-btn');
                    if (cascadeBtn) {
                        cascadeBtn.disabled = true;
                    }
                }

                // Update table data
                this.updateTableData(chartType);
            });
        }
    }

    fadeTransition(fromElement, toElement, callback) {
        // Add exit animation to current element
        fromElement.classList.add('chart-view-exit-active');

        setTimeout(() => {
            // Hide the outgoing element and show the incoming element
            fromElement.style.display = 'none';
            fromElement.classList.remove('chart-view-exit-active');

            toElement.style.display = 'block';
            toElement.classList.add('table-view-enter');

            // Force reflow to ensure the enter class is applied
            toElement.offsetHeight;

            // Add enter animation
            toElement.classList.add('table-view-enter-active');
            toElement.classList.remove('table-view-enter');

            // Execute callback
            if (callback) callback();

            // Clean up transition classes
            setTimeout(() => {
                toElement.classList.remove('table-view-enter-active');
            }, 300);

        }, 150); // Half of the transition duration for overlap effect
    }

    updateTableData(chartType) {
        if (!this.apiData) return;

        const tableId = chartType.replace('Chart', 'Table');
        const tableBodyId = tableId + 'Body';
        const tableBody = document.getElementById(tableBodyId);

        if (!tableBody) return;

        // Clear existing data
        tableBody.innerHTML = '';

        // Get data based on chart type
        let data = [];
        let dataKey = '';

        switch (chartType) {
            case 'timeSeriesChart':
                data = this.getTimeSeriesTableData();
                break;
            case 'keyChart':
                data = this.getKeyTableData();
                break;
            case 'deviceChart':
                data = this.getDeviceTableData();
                break;
            case 'browserChart':
                data = this.getBrowserTableData();
                break;
            case 'osChart':
                data = this.getOsTableData();
                break;
            case 'referrerChart':
                data = this.getReferrerTableData();
                break;
            case 'countryChart':
                data = this.getCountryTableData();
                break;
        }

        // Populate table
        if (data.length === 0) {
            tableBody.innerHTML = '<div class="table-empty">No data available for the selected time range</div>';
            return;
        }

        data.forEach(item => {
            const row = document.createElement('div');
            row.className = 'table-row';
            row.innerHTML = `
                <div class="table-cell">${this.escapeHtml(item.label)}</div>
                <div class="table-cell">${this.formatNumber(item.clicks)}</div>
                <div class="table-cell">${this.formatNumber(item.unique_clicks)}</div>
            `;
            tableBody.appendChild(row);
        });
    }

    getTimeSeriesTableData() {
        const clicksByTime = this.apiData.metrics?.clicks_by_time || [];
        const uniqueClicksByTime = this.apiData.metrics?.unique_clicks_by_time || [];

        return clicksByTime.map((item, index) => ({
            label: item.time || item.date || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByTime[index]?.unique_clicks || uniqueClicksByTime[index]?.value || 0
        }));
    }

    getKeyTableData() {
        const clicksByKey = this.apiData.metrics?.clicks_by_key || [];
        const uniqueClicksByKey = this.apiData.metrics?.unique_clicks_by_key || [];

        // Create a map for quick lookup of unique clicks by key
        const uniqueClicksMap = new Map();
        uniqueClicksByKey.forEach(item => {
            uniqueClicksMap.set(item.key, item.unique_clicks || item.value || 0);
        });

        return clicksByKey.map(item => ({
            label: item.key || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksMap.get(item.key) || 0
        }));
    }

    getDeviceTableData() {
        const clicksByDevice = this.apiData.metrics?.clicks_by_device || [];
        const uniqueClicksByDevice = this.apiData.metrics?.unique_clicks_by_device || [];

        return clicksByDevice.map((item, index) => ({
            label: item.device || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByDevice[index]?.unique_clicks || uniqueClicksByDevice[index]?.value || 0
        }));
    }

    getBrowserTableData() {
        const clicksByBrowser = this.apiData.metrics?.clicks_by_browser || [];
        const uniqueClicksByBrowser = this.apiData.metrics?.unique_clicks_by_browser || [];

        return clicksByBrowser.map((item, index) => ({
            label: item.browser || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByBrowser[index]?.unique_clicks || uniqueClicksByBrowser[index]?.value || 0
        }));
    }

    getOsTableData() {
        const clicksByOs = this.apiData.metrics?.clicks_by_os || [];
        const uniqueClicksByOs = this.apiData.metrics?.unique_clicks_by_os || [];

        return clicksByOs.map((item, index) => ({
            label: item.os || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByOs[index]?.unique_clicks || uniqueClicksByOs[index]?.value || 0
        }));
    }

    getReferrerTableData() {
        const clicksByReferrer = this.apiData.metrics?.clicks_by_referrer || [];
        const uniqueClicksByReferrer = this.apiData.metrics?.unique_clicks_by_referrer || [];

        return clicksByReferrer.map((item, index) => ({
            label: item.referrer || 'Direct',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByReferrer[index]?.unique_clicks || uniqueClicksByReferrer[index]?.value || 0
        }));
    }

    getCountryTableData() {
        const clicksByCountry = this.apiData.metrics?.clicks_by_country || [];
        const uniqueClicksByCountry = this.apiData.metrics?.unique_clicks_by_country || [];

        return clicksByCountry.map((item, index) => ({
            label: item.country || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByCountry[index]?.unique_clicks || uniqueClicksByCountry[index]?.value || 0
        }));
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateChartByType(chartType, value) {
        if (!this.apiData) return;

        switch (chartType) {
            case 'timeSeriesChart':
                this.updateTimeSeriesChart(this.apiData, value);
                break;
            case 'keyChart':
                this.updateKeyChart(this.apiData, value);
                break;
            case 'deviceChart':
                this.updateDeviceChart(this.apiData, value);
                break;
            case 'browserChart':
                this.updateBrowserChart(this.apiData, value);
                break;
            case 'osChart':
                this.updateOsChart(this.apiData, value);
                break;
            case 'referrerChart':
                this.updateReferrerChart(this.apiData, value);
                break;
            case 'countryChart':
                this.updateCountryChart(this.apiData, value);
                break;
        }

        // Update table data if table is currently visible
        const tableBtn = document.querySelector(`[data-chart="${chartType}"].table-view-btn`);
        if (tableBtn && tableBtn.classList.contains('active')) {
            this.updateTableData(chartType);
        }
    }

    async loadDashboardData() {
        try {
            const params = new URLSearchParams({
                scope: 'all',
                group_by: 'time,browser,os,country,referrer,device,key',
                metrics: 'clicks,unique_clicks'
            });

            // Always send specific start_date and end_date in UTC format
            // Use the date range picker's built-in functionality to get current range
            let startDate, endDate;
            
            if (this.startDate && this.endDate) {
                // Use provided datetime range
                startDate = new Date(this.startDate);
                endDate = new Date(this.endDate);
            } else {
                // Get current range from date range picker (handles both relative and custom ranges)
                const currentRange = this.dateRangePicker.getCurrentRange();
                startDate = new Date(currentRange.start);
                endDate = new Date(currentRange.end);
            }

            // Send full ISO datetime strings in UTC (preserving time component)
            params.append('start_date', startDate.toISOString());
            params.append('end_date', endDate.toISOString());

            console.log('Sending API request with dates:', {
                start_date: startDate.toISOString(),
                end_date: endDate.toISOString(),
                original_range: this.currentTimeRange
            });

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

        // Update any visible tables
        document.querySelectorAll('.table-view-btn.active').forEach(btn => {
            const chartType = btn.dataset.chart;
            this.updateTableData(chartType);
        });
    }

    updateTimeSeriesChart(data, option = null) {
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
        const dataOption = option || document.querySelector('[data-chart="timeSeriesChart"] .cascade-btn')?.dataset.value || 'compare';

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
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
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

    updateBrowserChart(data, option = null) {
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

        const dataOption = option || document.querySelector('[data-chart="browserChart"] .cascade-btn')?.dataset.value || 'compare';
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
                        stacked: dataOption === 'compare',
                        ticks: { color: '#fff' },
                        grid: { display: false }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
                    },
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

    updateOsChart(data, option = null) {
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

        const dataOption = option || document.querySelector('[data-chart="osChart"] .cascade-btn')?.dataset.value || 'compare';
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
                        stacked: dataOption === 'compare',
                        ticks: { color: '#fff' },
                        grid: { display: false }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
                    },
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

    updateReferrerChart(data, option = null) {
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

        const dataOption = option || document.querySelector('[data-chart="referrerChart"] .cascade-btn')?.dataset.value || 'compare';
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
                        stacked: dataOption === 'compare',
                        ticks: { color: '#fff' },
                        grid: { display: false }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
                    },
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

    updateCountryChart(data, option = null) {
        const countryChartContainer = document.getElementById('countryChart');
        countryChartContainer.innerHTML = ''; // Clear previous map

        // Extract country data from metrics
        const clicksByCountry = data.metrics?.clicks_by_country || [];
        const uniqueClicksByCountry = data.metrics?.unique_clicks_by_country || [];

        const dataOption = option || document.querySelector('[data-chart="countryChart"] .cascade-btn')?.dataset.value || 'total';
        const countryData = dataOption === 'unique' ? uniqueClicksByCountry : clicksByCountry;

        // Convert to AnyChart format: array of {id: 'country_code', value: clicks}
        const mapData = countryData.map(item => ({
            id: item.country, // Assuming country codes are provided
            value: item.clicks || item.unique_clicks
        }));

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

        series.tooltip().format(function (e) {
            return "Clicks: <b>" + e.getData("value") + "</b>";
        });

        var title = map.title();
        title.enabled(false);

        map.tooltip().useHtml(true);

        map.colorRange().enabled(true);
        map.colorRange().orientation('bottom');
        map.colorRange().labels({ 'fontSize': 13, 'fontColor': 'white' });
        map.colorRange().stroke('', 0.5, '5 2', 'round');

        var grids = map.grids();
        grids.enabled(true);
        grids.stroke("rgba(255, 255, 255, 0.1)", 0.5, "10 2", "round");

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

    updateDeviceChart(data, option = null) {
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

        const dataOption = option || document.querySelector('[data-chart="deviceChart"] .cascade-btn')?.dataset.value || 'compare';
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
                        stacked: dataOption === 'compare',
                        ticks: { color: '#fff' },
                        grid: { display: false }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
                    },
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

    updateKeyChart(data, option = null) {
        const canvas = document.getElementById('keyChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('key')) {
            this.charts.get('key').destroy();
        }

        // Extract key data from metrics
        const clicksByKey = data.metrics?.clicks_by_key || [];
        const uniqueClicksByKey = data.metrics?.unique_clicks_by_key || [];

        const dataOption = option || document.querySelector('[data-chart="keyChart"] .cascade-btn')?.dataset.value || 'compare';

        // Take top 10 keys for display
        const topClicksByKey = clicksByKey.slice(0, 10);
        const topUniqueClicksByKey = uniqueClicksByKey.slice(0, 10);
        
        const keyLabels = topClicksByKey.map(item => item.key);
        const totalClicksData = topClicksByKey.map(item => item.clicks);
        const uniqueClicksData = topUniqueClicksByKey.map(item => item.unique_clicks);

        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Total Clicks',
                data: totalClicksData,
                backgroundColor: 'rgba(255, 193, 7, 0.6)',
                borderColor: 'rgba(255, 193, 7, 1)',
                borderWidth: 2,
                borderRadius: 6,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Clicks',
                data: uniqueClicksData,
                backgroundColor: 'rgba(156, 39, 176, 0.6)',
                borderColor: 'rgba(156, 39, 176, 1)',
                borderWidth: 2,
                borderRadius: 6,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: keyLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    },
                    y: {
                        stacked: dataOption === 'compare',
                        ticks: {
                            color: '#fff',
                            maxTicksLimit: 10
                        },
                        grid: { display: false }
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff', boxWidth: 12, boxHeight: 12, padding: 10, useBorderRadius: true, borderRadius: 2, padding: 20 },
                        position: "bottom",
                        align: "start",
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        callbacks: {
                            afterBody: function (context) {
                                const index = context[0].dataIndex;
                                const item = topClicksByKey[index];
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
        // Auto-refresh dropdown items
        const refreshDropdown = document.querySelector('.auto-refresh-dropdown .dropdown-menu');
        if (refreshDropdown) {
            refreshDropdown.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const item = e.target.closest('.dropdown-item');
                if (item && !item.classList.contains('disabled')) {
                    const interval = parseInt(item.dataset.interval);
                    this.setAutoRefreshInterval(interval);

                    // Update button text
                    const autoRefreshBtn = document.querySelector('.auto-refresh-btn');
                    const intervalText = item.textContent.trim();
                    autoRefreshBtn.innerHTML = `${intervalText} <i class="ti ti-chevron-down"></i>`;

                    // Close dropdown
                    const dropdown = refreshDropdown;
                    dropdown.classList.remove('show');
                }
            });
        }
    }

    setAutoRefreshInterval(seconds) {
        // Clear existing interval
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }

        // Save to localStorage
        if (seconds > 0) {
            localStorage.setItem('stats-auto-refresh-interval', seconds.toString());
        } else {
            localStorage.removeItem('stats-auto-refresh-interval');
        }

        // Set new interval if seconds > 0
        if (seconds > 0) {
            const milliseconds = seconds * 1000;
            this.autoRefreshInterval = setInterval(() => {
                this.loadDashboardData();
            }, milliseconds);

            console.log(`Auto-refresh set to ${seconds} seconds`);
        } else {
            console.log('Auto-refresh disabled');
        }
    }

    restoreAutoRefreshSetting() {
        // Get saved auto-refresh interval from localStorage
        const savedInterval = localStorage.getItem('stats-auto-refresh-interval');
        
        if (savedInterval !== null) {
            const intervalSeconds = parseInt(savedInterval);
            
            // Find the corresponding dropdown item
            const dropdownItem = document.querySelector(`[data-interval="${intervalSeconds}"]`);
            if (dropdownItem) {
                // Update the button text
                const autoRefreshBtn = document.querySelector('.auto-refresh-btn');
                const intervalText = dropdownItem.textContent.trim();
                autoRefreshBtn.innerHTML = `${intervalText} <i class="ti ti-chevron-down"></i>`;
                
                // Set the auto-refresh interval
                this.setAutoRefreshInterval(intervalSeconds);
            }
        }
    }

    showError(message) {
        console.error(message);
        // You can implement a toast notification here
        alert(message); // Simple fallback
    }

    destroy() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
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