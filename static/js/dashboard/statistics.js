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

        // Filter system
        this.filterManager = new FilterManager();
        this.availableOptions = {
            browser: [],
            os: [],
            // device: [], // DISABLED: Reliable device detection not available yet
            country: [],
            city: [],
            referrer: [],
            key: []
        };
        this.pendingChanges = new Set(); // Track which categories have pending changes
        this.currentFilterType = null; // Track which filter type is currently being edited

        this.init();
    }

    /**
     * Format time labels based on bucket strategy for better readability
     * @param {string} timeValue - Raw time value from API
     * @param {string} bucketStrategy - The bucketing strategy used ('10_minute', 'hourly', 'daily', etc.)
     * @returns {string} - Formatted human-readable label
     */
    formatTimeLabel(timeValue, bucketStrategy) {
        if (!timeValue) return timeValue;

        try {
            const date = dayjs(timeValue);

            switch (bucketStrategy) {
                case '10_minute':
                case 'hourly':
                    // For hourly: "1:00 AM", "2:00 PM", etc.
                    return date.format('h:mm A');

                case 'daily':
                    // For daily: "Aug 12", "Sep 11", etc.
                    return date.format('MMM D');

                case 'weekly':
                    // For weekly: "Week 32", "Week 33", etc.
                    return `Week ${date.week()}`;

                case 'monthly':
                    // For monthly: "Aug 2025", "Sep 2025", etc.
                    return date.format('MMM YYYY');

                default:
                    // Fallback to daily format
                    return date.format('MMM D');
            }
        } catch (error) {
            console.warn('Error formatting time label:', error);
            return timeValue; // Return original if parsing fails
        }
    }

    // Comprehensive country code to name mapping
    getCountryName(countryCode) {
        const countryMap = {
            'AD': 'Andorra', 'AE': 'United Arab Emirates', 'AF': 'Afghanistan', 'AG': 'Antigua and Barbuda',
            'AI': 'Anguilla', 'AL': 'Albania', 'AM': 'Armenia', 'AO': 'Angola', 'AQ': 'Antarctica',
            'AR': 'Argentina', 'AS': 'American Samoa', 'AT': 'Austria', 'AU': 'Australia', 'AW': 'Aruba',
            'AX': 'Åland Islands', 'AZ': 'Azerbaijan', 'BA': 'Bosnia and Herzegovina', 'BB': 'Barbados',
            'BD': 'Bangladesh', 'BE': 'Belgium', 'BF': 'Burkina Faso', 'BG': 'Bulgaria', 'BH': 'Bahrain',
            'BI': 'Burundi', 'BJ': 'Benin', 'BL': 'Saint Barthélemy', 'BM': 'Bermuda', 'BN': 'Brunei',
            'BO': 'Bolivia', 'BQ': 'Caribbean Netherlands', 'BR': 'Brazil', 'BS': 'Bahamas', 'BT': 'Bhutan',
            'BV': 'Bouvet Island', 'BW': 'Botswana', 'BY': 'Belarus', 'BZ': 'Belize', 'CA': 'Canada',
            'CC': 'Cocos Islands', 'CD': 'Democratic Republic of the Congo', 'CF': 'Central African Republic',
            'CG': 'Republic of the Congo', 'CH': 'Switzerland', 'CI': 'Côte d\'Ivoire', 'CK': 'Cook Islands',
            'CL': 'Chile', 'CM': 'Cameroon', 'CN': 'China', 'CO': 'Colombia', 'CR': 'Costa Rica',
            'CU': 'Cuba', 'CV': 'Cape Verde', 'CW': 'Curaçao', 'CX': 'Christmas Island', 'CY': 'Cyprus',
            'CZ': 'Czech Republic', 'DE': 'Germany', 'DJ': 'Djibouti', 'DK': 'Denmark', 'DM': 'Dominica',
            'DO': 'Dominican Republic', 'DZ': 'Algeria', 'EC': 'Ecuador', 'EE': 'Estonia', 'EG': 'Egypt',
            'EH': 'Western Sahara', 'ER': 'Eritrea', 'ES': 'Spain', 'ET': 'Ethiopia', 'FI': 'Finland',
            'FJ': 'Fiji', 'FK': 'Falkland Islands', 'FM': 'Micronesia', 'FO': 'Faroe Islands', 'FR': 'France',
            'GA': 'Gabon', 'GB': 'United Kingdom', 'GD': 'Grenada', 'GE': 'Georgia', 'GF': 'French Guiana',
            'GG': 'Guernsey', 'GH': 'Ghana', 'GI': 'Gibraltar', 'GL': 'Greenland', 'GM': 'Gambia',
            'GN': 'Guinea', 'GP': 'Guadeloupe', 'GQ': 'Equatorial Guinea', 'GR': 'Greece', 'GS': 'South Georgia',
            'GT': 'Guatemala', 'GU': 'Guam', 'GW': 'Guinea-Bissau', 'GY': 'Guyana', 'HK': 'Hong Kong',
            'HM': 'Heard Island', 'HN': 'Honduras', 'HR': 'Croatia', 'HT': 'Haiti', 'HU': 'Hungary',
            'ID': 'Indonesia', 'IE': 'Ireland', 'IL': 'Israel', 'IM': 'Isle of Man', 'IN': 'India',
            'IO': 'British Indian Ocean Territory', 'IQ': 'Iraq', 'IR': 'Iran', 'IS': 'Iceland', 'IT': 'Italy',
            'JE': 'Jersey', 'JM': 'Jamaica', 'JO': 'Jordan', 'JP': 'Japan', 'KE': 'Kenya', 'KG': 'Kyrgyzstan',
            'KH': 'Cambodia', 'KI': 'Kiribati', 'KM': 'Comoros', 'KN': 'Saint Kitts and Nevis', 'KP': 'North Korea',
            'KR': 'South Korea', 'KW': 'Kuwait', 'KY': 'Cayman Islands', 'KZ': 'Kazakhstan', 'LA': 'Laos',
            'LB': 'Lebanon', 'LC': 'Saint Lucia', 'LI': 'Liechtenstein', 'LK': 'Sri Lanka', 'LR': 'Liberia',
            'LS': 'Lesotho', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'LV': 'Latvia', 'LY': 'Libya',
            'MA': 'Morocco', 'MC': 'Monaco', 'MD': 'Moldova', 'ME': 'Montenegro', 'MF': 'Saint Martin',
            'MG': 'Madagascar', 'MH': 'Marshall Islands', 'MK': 'North Macedonia', 'ML': 'Mali', 'MM': 'Myanmar',
            'MN': 'Mongolia', 'MO': 'Macao', 'MP': 'Northern Mariana Islands', 'MQ': 'Martinique', 'MR': 'Mauritania',
            'MS': 'Montserrat', 'MT': 'Malta', 'MU': 'Mauritius', 'MV': 'Maldives', 'MW': 'Malawi',
            'MX': 'Mexico', 'MY': 'Malaysia', 'MZ': 'Mozambique', 'NA': 'Namibia', 'NC': 'New Caledonia',
            'NE': 'Niger', 'NF': 'Norfolk Island', 'NG': 'Nigeria', 'NI': 'Nicaragua', 'NL': 'Netherlands',
            'NO': 'Norway', 'NP': 'Nepal', 'NR': 'Nauru', 'NU': 'Niue', 'NZ': 'New Zealand', 'OM': 'Oman',
            'PA': 'Panama', 'PE': 'Peru', 'PF': 'French Polynesia', 'PG': 'Papua New Guinea', 'PH': 'Philippines',
            'PK': 'Pakistan', 'PL': 'Poland', 'PM': 'Saint Pierre and Miquelon', 'PN': 'Pitcairn Islands',
            'PR': 'Puerto Rico', 'PS': 'Palestine', 'PT': 'Portugal', 'PW': 'Palau', 'PY': 'Paraguay',
            'QA': 'Qatar', 'RE': 'Réunion', 'RO': 'Romania', 'RS': 'Serbia', 'RU': 'Russia', 'RW': 'Rwanda',
            'SA': 'Saudi Arabia', 'SB': 'Solomon Islands', 'SC': 'Seychelles', 'SD': 'Sudan', 'SE': 'Sweden',
            'SG': 'Singapore', 'SH': 'Saint Helena', 'SI': 'Slovenia', 'SJ': 'Svalbard and Jan Mayen',
            'SK': 'Slovakia', 'SL': 'Sierra Leone', 'SM': 'San Marino', 'SN': 'Senegal', 'SO': 'Somalia',
            'SR': 'Suriname', 'SS': 'South Sudan', 'ST': 'São Tomé and Príncipe', 'SV': 'El Salvador',
            'SX': 'Sint Maarten', 'SY': 'Syria', 'SZ': 'Eswatini', 'TC': 'Turks and Caicos Islands',
            'TD': 'Chad', 'TF': 'French Southern Territories', 'TG': 'Togo', 'TH': 'Thailand', 'TJ': 'Tajikistan',
            'TK': 'Tokelau', 'TL': 'Timor-Leste', 'TM': 'Turkmenistan', 'TN': 'Tunisia', 'TO': 'Tonga',
            'TR': 'Turkey', 'TT': 'Trinidad and Tobago', 'TV': 'Tuvalu', 'TW': 'Taiwan', 'TZ': 'Tanzania',
            'UA': 'Ukraine', 'UG': 'Uganda', 'UM': 'United States Minor Outlying Islands', 'US': 'United States',
            'UY': 'Uruguay', 'UZ': 'Uzbekistan', 'VA': 'Vatican City', 'VC': 'Saint Vincent and the Grenadines',
            'VE': 'Venezuela', 'VG': 'British Virgin Islands', 'VI': 'United States Virgin Islands',
            'VN': 'Vietnam', 'VU': 'Vanuatu', 'WF': 'Wallis and Futuna', 'WS': 'Samoa', 'YE': 'Yemen',
            'YT': 'Mayotte', 'ZA': 'South Africa', 'ZM': 'Zambia', 'ZW': 'Zimbabwe', 'XX': 'Unknown'
        };
        return countryMap[countryCode] || countryCode;
    }

    init() {
        this.setupDateRangePicker();
        this.setupEventListeners();
        this.setupFilterSystem();
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

    setupFilterSystem() {
        // Set up filter toggle
        const filtersBtn = document.querySelector('.filters-btn');
        const filtersDropdown = document.querySelector('.filters-dropdown');

        if (filtersBtn && filtersDropdown) {
            filtersBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const isOpen = filtersDropdown.classList.contains('show');

                if (isOpen) {
                    filtersDropdown.classList.remove('show');
                    filtersBtn.classList.remove('active');
                } else {
                    filtersDropdown.classList.add('show');
                    filtersBtn.classList.add('active');
                }
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.filters-dropdown-container')) {
                const filtersDropdown = document.querySelector('.filters-dropdown');
                const filtersBtn = document.querySelector('.filters-btn');

                if (filtersDropdown && filtersBtn) {
                    filtersDropdown.classList.remove('show');
                    filtersBtn.classList.remove('active');
                }
            }
        });

        // Set up hierarchical filter navigation
        this.setupHierarchicalFilters();

        // Set up filter change listeners
        this.filterManager.onFiltersChanged = () => {
            this.updateFilterUI();
            this.loadDashboardData();
        };
    }

    setupHierarchicalFilters() {
        // Set up filter type item clicks
        const filterTypeItems = document.querySelectorAll('.filter-type-item:not(.clear-all-item)');
        filterTypeItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const filterType = item.dataset.filter;
                this.showFilterValues(filterType);
            });
        });

        // Set up clear all button
        const clearAllItem = document.querySelector('.filter-type-item.clear-all-item');
        if (clearAllItem) {
            clearAllItem.addEventListener('click', (e) => {
                e.preventDefault();
                this.filterManager.clearAllFilters();
                this.closeFiltersDropdown();
            });
        }

        // Set up back button
        const backBtn = document.querySelector('.back-btn');
        if (backBtn) {
            backBtn.addEventListener('click', (e) => {
                e.preventDefault();
                // If there are pending changes for current type, apply and go back
                if (this.currentFilterType && this.pendingChanges.has(this.currentFilterType)) {
                    this.pendingChanges.delete(this.currentFilterType);
                    this.filterManager.notifyChange();
                }
                this.showFilterTypes();
            });
        }

        // Set up search in values view
        const valuesSearchInput = document.querySelector('.values-search-input');
        if (valuesSearchInput) {
            valuesSearchInput.addEventListener('input', (e) => {
                if (this.currentFilterType) {
                    this.filterValuesOptions(this.currentFilterType, e.target.value);
                }
            });
        }
    }

    showFilterValues(filterType) {
        this.currentFilterType = filterType;

        // Hide main list, show values view
        const typesList = document.querySelector('.filter-types-list');
        const valuesView = document.querySelector('.filter-values-view');
        const backBtn = document.querySelector('.back-btn');

        if (typesList && valuesView) {
            // exit current view
            typesList.classList.add('view-exit-active');

            setTimeout(() => {
                typesList.style.display = 'none';
                typesList.classList.remove('view-exit-active');

                valuesView.style.display = 'block';
                valuesView.classList.add('view-enter');

                // force reflow
                valuesView.offsetHeight;
                valuesView.classList.add('view-enter-active');
                valuesView.classList.remove('view-enter');

                setTimeout(() => {
                    valuesView.classList.remove('view-enter-active');
                }, 200);
            }, 80);

            // Populate values
            this.populateFilterValues(filterType);

            // Clear and focus search
            const searchInput = valuesView.querySelector('.values-search-input');
            if (searchInput) {
                searchInput.value = '';
                setTimeout(() => searchInput.focus(), 100);
            }

            // Ensure back button shows arrow initially (no pending yet)
            if (backBtn) {
                this.setBackButtonApplyState(false);
            }
        }
    }

    showFilterTypes() {
        // Apply pending changes if any
        if (this.currentFilterType && this.pendingChanges.has(this.currentFilterType)) {
            this.pendingChanges.delete(this.currentFilterType);
            this.filterManager.notifyChange();
        }

        this.currentFilterType = null;

        // Hide values view, show main list
        const typesList = document.querySelector('.filter-types-list');
        const valuesView = document.querySelector('.filter-values-view');
        const backBtn = document.querySelector('.back-btn');

        if (typesList && valuesView) {
            valuesView.classList.add('view-exit-active');

            setTimeout(() => {
                valuesView.style.display = 'none';
                valuesView.classList.remove('view-exit-active');

                typesList.style.display = 'block';
                typesList.classList.add('view-enter');
                typesList.offsetHeight;
                typesList.classList.add('view-enter-active');
                typesList.classList.remove('view-enter');

                setTimeout(() => {
                    typesList.classList.remove('view-enter-active');
                }, 200);
            }, 80);
        }

        // Reset back button to arrow
        if (backBtn) {
            this.setBackButtonApplyState(false);
        }
    }

    setBackButtonApplyState(shouldApply) {
        const backBtn = document.querySelector('.back-btn');
        if (!backBtn) return;
        const icon = backBtn.querySelector('i');
        if (!icon) return;
        if (shouldApply) {
            icon.className = 'ti ti-check';
            backBtn.title = 'Apply & Back';
        } else {
            icon.className = 'ti ti-arrow-left';
            backBtn.title = 'Back';
        }
    }

    closeFiltersDropdown() {
        const filtersDropdown = document.querySelector('.filters-dropdown');
        const filtersBtn = document.querySelector('.filters-btn');

        if (filtersDropdown && filtersBtn) {
            filtersDropdown.classList.remove('show');
            filtersBtn.classList.remove('active');

            // Reset to main view
            this.showFilterTypes();
        }
    }



    populateFilterValues(filterType) {
        const valuesList = document.querySelector('.filter-values-list');
        if (!valuesList) return;

        valuesList.innerHTML = '';

        const options = this.availableOptions[filterType] || [];
        if (options.length === 0) {
            valuesList.innerHTML = '<div class="empty">No data available</div>';
            return;
        }

        options.forEach(option => {
            const optionElement = this.createFilterValueElement(filterType, option);
            valuesList.appendChild(optionElement);
        });
    }

    createFilterValueElement(type, option) {
        const label = document.createElement('label');
        label.className = 'option-item';

        const isSelected = this.filterManager.isSelected(type, option.value);

        label.innerHTML = `
            <input type="checkbox" ${isSelected ? 'checked' : ''} data-value="${option.value}">
            <span class="checkmark"></span>
            <span class="option-text">${this.escapeHtml(option.label)}</span>
            <span class="option-count">${this.formatNumber(option.count)}</span>
        `;

        // Add change listener
        const checkbox = label.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.filterManager.addFilter(type, option.value);
            } else {
                this.filterManager.removeFilter(type, option.value);
            }

            // Mark this category as having pending changes
            this.pendingChanges.add(type);
            this.setBackButtonApplyState(true);

            // Update the main list summary
            this.updateFilterTypeStatus(type);
        });

        return label;
    }

    filterValuesOptions(type, searchTerm) {
        const valuesList = document.querySelector('.filter-values-list');
        if (!valuesList) return;

        const options = valuesList.querySelectorAll('.option-item');
        const term = searchTerm.toLowerCase();

        options.forEach(option => {
            const text = option.querySelector('.option-text').textContent.toLowerCase();
            if (text.includes(term)) {
                option.style.display = 'flex';
            } else {
                option.style.display = 'none';
            }
        });
    }

    updateFilterTypeStatus(type) {
        const typeItem = document.querySelector(`[data-filter="${type}"]`);
        const countElement = typeItem?.querySelector('.filter-count');

        if (!countElement) return;

        const activeFilters = this.filterManager.getActiveFilters()[type] || [];

        if (activeFilters.length === 0) {
            countElement.textContent = 'All';
            countElement.style.background = 'rgba(255, 255, 255, 0.08)';
            countElement.style.color = 'rgba(255, 255, 255, 0.6)';
        } else {
            countElement.textContent = activeFilters.length.toString();
            countElement.style.background = 'rgba(124, 58, 237, 0.2)';
            countElement.style.color = 'rgba(124, 58, 237, 1)';
        }
    }

    initializeFilterLoadingState() {
        const filterTypes = ['browser', 'os', 'country', 'city', 'referrer', 'key'];

        filterTypes.forEach(type => {
            const optionsList = document.querySelector(`[data-filter="${type}"] .options-list`);
            if (optionsList) {
                optionsList.innerHTML = '<div class="loading">Loading options...</div>';
                optionsList.classList.add('loading');
            }
        });
    }

    setupMultiSelectDropdowns() {
        const wrappers = document.querySelectorAll('.multi-select-wrapper');

        wrappers.forEach(wrapper => {
            const trigger = wrapper.querySelector('.multi-select-trigger');
            const dropdown = wrapper.querySelector('.multi-select-dropdown');
            const filterType = wrapper.dataset.filter;

            if (trigger && dropdown) {
                // Toggle dropdown
                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();

                    // Close other dropdowns
                    document.querySelectorAll('.multi-select-dropdown.show').forEach(dd => {
                        if (dd !== dropdown) {
                            dd.classList.remove('show');
                            const parentWrapper = dd.parentElement;
                            parentWrapper.querySelector('.multi-select-trigger').classList.remove('active');
                            parentWrapper.classList.remove('active');
                        }
                    });

                    // Toggle current dropdown
                    const isOpen = dropdown.classList.contains('show');
                    if (isOpen) {
                        dropdown.classList.remove('show');
                        trigger.classList.remove('active');
                        wrapper.classList.remove('active');

                        // Apply filters when dropdown closes if there are changes for this category
                        if (this.pendingChanges.has(filterType)) {
                            this.pendingChanges.delete(filterType);
                            this.filterManager.notifyChange();
                        }
                    } else {
                        dropdown.classList.add('show');
                        trigger.classList.add('active');
                        wrapper.classList.add('active');

                        // Focus search input
                        const searchInput = dropdown.querySelector('.search-input');
                        if (searchInput) {
                            setTimeout(() => searchInput.focus(), 100);
                        }
                    }
                });

                // Set up search functionality
                const searchInput = dropdown.querySelector('.search-input');
                if (searchInput) {
                    searchInput.addEventListener('input', (e) => {
                        this.filterOptions(filterType, e.target.value);
                    });
                }

                // Set up select all / clear all buttons
                const selectAllBtn = dropdown.querySelector('.select-all-btn');
                const clearAllBtn = dropdown.querySelector('.clear-all-btn');

                if (selectAllBtn) {
                    selectAllBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.selectAllOptions(filterType);
                    });
                }

                if (clearAllBtn) {
                    clearAllBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.clearAllOptions(filterType);
                    });
                }
            }
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.multi-select-wrapper')) {
                document.querySelectorAll('.multi-select-dropdown.show').forEach(dropdown => {
                    dropdown.classList.remove('show');
                    const parentWrapper = dropdown.parentElement;
                    const filterType = parentWrapper.dataset.filter;

                    parentWrapper.querySelector('.multi-select-trigger').classList.remove('active');
                    parentWrapper.classList.remove('active');

                    // Apply filters when dropdown closes if there are changes for this category
                    if (this.pendingChanges.has(filterType)) {
                        this.pendingChanges.delete(filterType);
                        this.filterManager.notifyChange();
                    }
                });
            }
        });
    }

    setupFilterActions() {
        const clearAllBtn = document.querySelector('.clear-all-filters-btn');

        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.filterManager.clearAllFilters();
            });
        }
    }

    populateFilterOptions(data) {

        // Extract available options from API data
        const filterTypes = ['browser', 'os', 'country', 'city', 'referrer', 'key'];

        filterTypes.forEach(type => {
            const metricKey = `clicks_by_${type}`;
            const options = data.metrics?.[metricKey] || [];

            this.availableOptions[type] = options.map(item => {
                if (type === 'country') {
                    // For countries, use country name as both value and label
                    const countryName = this.getCountryName(item[type]);
                    return {
                        value: countryName,
                        label: countryName,
                        code: item[type], // Keep the code for reference
                        count: item.clicks || item.total_clicks || 0
                    };
                } else if (type === 'key') {
                    // For keys, handle both "key" and "short_code" fields
                    const keyValue = item.key || item.short_code || item[type];
                    return {
                        value: keyValue,
                        label: keyValue,
                        count: item.clicks || item.total_clicks || 0
                    };
                } else {
                    return {
                        value: item[type],
                        label: item[type],
                        count: item.clicks || item.total_clicks || 0
                    };
                }
            }).filter(option => option.value)
                .sort((a, b) => b.count - a.count); // Sort by count descending
        });

        // Update filter type statuses in main list
        this.updateAllFilterTypeStatuses();
    }

    updateAllFilterTypeStatuses() {
        const filterTypes = ['browser', 'os', 'country', 'city', 'referrer', 'key'];
        filterTypes.forEach(type => {
            this.updateFilterTypeStatus(type);
        });
    }

    renderFilterOptions() {
        const filterTypes = ['browser', 'os', 'country', 'city', 'referrer', 'key'];

        filterTypes.forEach(type => {
            const optionsList = document.querySelector(`[data-filter="${type}"] .options-list`);

            if (optionsList) {
                optionsList.innerHTML = '';
                optionsList.classList.remove('loading', 'empty');

                const options = this.availableOptions[type] || [];

                if (options.length === 0) {
                    optionsList.innerHTML = '<div class="empty">No data available</div>';
                    optionsList.classList.add('empty');
                    return;
                }

                options.forEach(option => {
                    const optionElement = this.createOptionElement(type, option);
                    optionsList.appendChild(optionElement);
                });
            } else {
                console.warn(`Options list not found for ${type}`);
            }
        });
    }

    createOptionElement(type, option) {
        const label = document.createElement('label');
        label.className = 'option-item';

        const isSelected = this.filterManager.isSelected(type, option.value);

        label.innerHTML = `
            <input type="checkbox" ${isSelected ? 'checked' : ''} data-value="${option.value}">
            <span class="checkmark"></span>
            <span class="option-text">${this.escapeHtml(option.label)}</span>
            <span class="option-count">${this.formatNumber(option.count)}</span>
        `;

        // Add change listener
        const checkbox = label.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.filterManager.addFilter(type, option.value);
            } else {
                this.filterManager.removeFilter(type, option.value);
            }

            // Mark this category as having pending changes
            this.pendingChanges.add(type);

            // Update the summary immediately for visual feedback
            this.updateFilterSummary(type);
        });

        return label;
    }

    filterOptions(type, searchTerm) {
        const optionsList = document.querySelector(`[data-filter="${type}"] .options-list`);
        if (!optionsList) return;

        const options = optionsList.querySelectorAll('.option-item');
        const term = searchTerm.toLowerCase();

        options.forEach(option => {
            const text = option.querySelector('.option-text').textContent.toLowerCase();
            if (text.includes(term)) {
                option.style.display = 'flex';
            } else {
                option.style.display = 'none';
            }
        });
    }

    updateFilterOptionsUI(type) {
        const optionsList = document.querySelector(`[data-filter="${type}"] .options-list`);
        if (!optionsList) {
            console.warn(`Options list not found for ${type}`);
            return;
        }

        const checkboxes = optionsList.querySelectorAll('input[type="checkbox"]');

        checkboxes.forEach(checkbox => {
            const value = checkbox.dataset.value;
            const isSelected = this.filterManager.isSelected(type, value);
            checkbox.checked = isSelected;
        });
    }

    updateFilterUI() {
        // Update active filter count
        const totalActiveFilters = this.filterManager.getTotalActiveFilters();
        const countElement = document.querySelector('.active-filters-count');

        if (countElement) {
            if (totalActiveFilters > 0) {
                countElement.textContent = totalActiveFilters;
                countElement.style.display = 'inline-block';
            } else {
                countElement.style.display = 'none';
            }
        }

        // Update filter summaries
        const filterTypes = ['browser', 'os', 'country', 'city', 'referrer', 'key'];
        filterTypes.forEach(type => {
            this.updateFilterSummary(type);
            this.updateFilterOptionsUI(type);
        });

        // Update clear all button state
        const clearAllBtn = document.querySelector('.clear-all-filters-btn');
        if (clearAllBtn) {
            clearAllBtn.disabled = totalActiveFilters === 0;
        }
    }

    updateFilterSummary(type) {
        const trigger = document.querySelector(`[data-filter="${type}"] .multi-select-trigger`);
        const summary = trigger?.querySelector('.selected-summary');

        if (!summary) return;

        const selectedFilters = this.filterManager.getActiveFilters()[type] || [];
        const typeLabels = {
            browser: 'browsers',
            os: 'systems',
            // device: 'devices', // DISABLED: Reliable device detection not available yet
            country: 'countries',
            city: 'cities',
            referrer: 'referrers',
            key: 'short URLs'
        };

        if (selectedFilters.length === 0) {
            summary.textContent = `All ${typeLabels[type]}`;
            trigger.classList.remove('active');
        } else if (selectedFilters.length === 1) {
            const option = this.availableOptions[type].find(opt => opt.value === selectedFilters[0]);
            summary.textContent = option ? option.label : selectedFilters[0];
            trigger.classList.add('active');
        } else if (selectedFilters.length <= 3) {
            const labels = selectedFilters.map(value => {
                const option = this.availableOptions[type].find(opt => opt.value === value);
                return option ? option.label : value;
            });
            summary.textContent = labels.join(', ');
            trigger.classList.add('active');
        } else {
            const firstTwo = selectedFilters.slice(0, 2).map(value => {
                const option = this.availableOptions[type].find(opt => opt.value === value);
                return option ? option.label : value;
            });
            summary.textContent = `${firstTwo.join(', ')} +${selectedFilters.length - 2}`;
            trigger.classList.add('active');
        }
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
            case 'cityChart':
                data = this.getCityTableData();
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

    getCityTableData() {
        const clicksByCity = this.apiData.metrics?.clicks_by_city || [];
        const uniqueClicksByCity = this.apiData.metrics?.unique_clicks_by_city || [];

        return clicksByCity.map((item, index) => ({
            label: item.city || 'Unknown',
            clicks: item.clicks || item.value || 0,
            unique_clicks: uniqueClicksByCity[index]?.unique_clicks || uniqueClicksByCity[index]?.value || 0
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
            label: this.getCountryName(item.country) || 'Unknown', // Convert country code to name for table
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
            case 'cityChart':
                this.updateCityChart(this.apiData, value);
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
                group_by: 'time,browser,os,country,city,referrer,key',
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

            // Add active filters to the request
            const activeFilters = this.filterManager.getActiveFilters();
            Object.keys(activeFilters).forEach(filterType => {
                const values = activeFilters[filterType];
                if (values && values.length > 0) {
                    params.append(filterType, values.join(','));
                }
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

            // Always populate filter options from API data
            this.populateFilterOptions(this.apiData);

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
        this.updateCityChart(data);
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

        // Get bucket strategy from API response for label formatting
        const bucketStrategy = data.time_bucket_info?.strategy || 'daily';

        // Convert to chart format with human-readable labels
        const rawLabels = clicksByTime.map(item => item.time || item.date);
        const labels = rawLabels.map(label => this.formatTimeLabel(label, bucketStrategy));
        const clicksData = clicksByTime.map(item => item.clicks !== undefined ? item.clicks : (item.value || 0));
        const uniqueClicksData = uniqueClicksByTime.map(item => item.unique_clicks !== undefined ? item.unique_clicks : (item.value || 0));

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
                tension: 0,
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
                tension: 0,
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
                pointStyle: false,
                scales: {
                    x: {
                        ticks: { color: '#fff', maxTicksLimit: 8 },
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
                        bodyColor: '#ffffff',
                        callbacks: {
                            title: (context) => {
                                // Show both formatted label and original timestamp
                                const index = context[0].dataIndex;
                                const formattedLabel = labels[index];
                                const originalTime = rawLabels[index];

                                // For hourly/10-minute, show date + time
                                if (bucketStrategy === 'hourly' || bucketStrategy === '10_minute') {
                                    const date = dayjs(originalTime);
                                    return `${date.format('MMM D, YYYY')} at ${formattedLabel}`;
                                }
                                // For daily, show full date
                                else if (bucketStrategy === 'daily') {
                                    const date = dayjs(originalTime);
                                    return `${formattedLabel}, ${date.format('YYYY')}`;
                                }
                                // For other strategies, use formatted label
                                else {
                                    return formattedLabel;
                                }
                            }
                        }
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
            id: item.country, // Use country code directly (now stored as codes)
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

    updateCityChart(data, option = null) {
        const canvas = document.getElementById('cityChart');
        const ctx = canvas.getContext('2d');

        if (this.charts.has('city')) {
            this.charts.get('city').destroy();
        }

        // Extract city data from metrics
        const clicksByCity = data.metrics?.clicks_by_city || [];
        const uniqueClicksByCity = data.metrics?.unique_clicks_by_city || [];

        // Convert to chart format
        const cityLabels = clicksByCity.map(item => item.city);
        const cityClicks = clicksByCity.map(item => item.clicks);
        const cityUniqueClicks = uniqueClicksByCity.map(item => item.unique_clicks);

        const dataOption = option || document.querySelector('[data-chart="cityChart"] .cascade-btn')?.dataset.value || 'compare';
        const datasets = [];

        if (dataOption === 'total' || dataOption === 'compare') {
            datasets.push({
                label: 'Cities',
                data: cityClicks,
                backgroundColor: 'rgba(75, 192, 192, 0.15)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Cities',
                data: cityUniqueClicks,
                backgroundColor: 'rgba(255, 99, 132, 0.25)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 2,
                borderRadius: 20,
            });
        }

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: cityLabels,
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

        this.charts.set('city', chart);
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
                borderRadius: 20,
            });
        }

        if (dataOption === 'unique' || dataOption === 'compare') {
            datasets.push({
                label: 'Unique Clicks',
                data: uniqueClicksData,
                backgroundColor: 'rgba(156, 39, 176, 0.6)',
                borderColor: 'rgba(156, 39, 176, 1)',
                borderWidth: 2,
                borderRadius: 20,
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

function updateCityChart() {
    if (window.dashboard && window.dashboard.apiData) {
        window.dashboard.updateCityChart(window.dashboard.apiData);
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

// Filter Manager Class
class FilterManager {
    constructor() {
        this.activeFilters = {
            browser: [],
            os: [],
            // device: [], // DISABLED: Reliable device detection not available yet
            country: [],
            city: [],
            referrer: [],
            key: []
        };
        this.onFiltersChanged = null;
    }

    addFilter(type, value) {
        if (!this.activeFilters[type]) {
            this.activeFilters[type] = [];
        }

        if (!this.activeFilters[type].includes(value)) {
            this.activeFilters[type].push(value);
            // Don't notify change immediately - wait for dropdown close
        }
    }

    removeFilter(type, value) {
        if (!this.activeFilters[type]) return;

        const index = this.activeFilters[type].indexOf(value);
        if (index > -1) {
            this.activeFilters[type].splice(index, 1);
            // Don't notify change immediately - wait for dropdown close
        }
    }

    clearFilter(type) {
        if (this.activeFilters[type] && this.activeFilters[type].length > 0) {
            this.activeFilters[type] = [];
            // Don't notify change immediately - wait for dropdown close
        }
    }

    clearAllFilters() {
        // Clear all active filters
        Object.keys(this.activeFilters).forEach(type => {
            this.activeFilters[type] = [];
        });

        // Immediately trigger data refresh for clear all
        this.notifyChange();
    }

    isSelected(type, value) {
        return this.activeFilters[type] && this.activeFilters[type].includes(value);
    }

    getActiveFilters() {
        return { ...this.activeFilters };
    }

    getTotalActiveFilters() {
        return Object.values(this.activeFilters).reduce((total, filters) => total + filters.length, 0);
    }

    notifyChange() {
        if (this.onFiltersChanged) {
            this.onFiltersChanged();
        } else {
            console.warn('FilterManager: onFiltersChanged callback not set');
        }
    }

    // Save filters to URL for sharing/bookmarking
    saveToURL() {
        const url = new URL(window.location);
        const params = url.searchParams;

        // Clear existing filter params
        Object.keys(this.activeFilters).forEach(type => {
            params.delete(type);
        });

        // Add active filters
        Object.keys(this.activeFilters).forEach(type => {
            if (this.activeFilters[type].length > 0) {
                params.set(type, this.activeFilters[type].join(','));
            }
        });

        // Update URL without reloading
        window.history.replaceState({}, '', url);
    }

    // Load filters from URL
    loadFromURL() {
        const params = new URLSearchParams(window.location.search);
        let hasFilters = false;

        Object.keys(this.activeFilters).forEach(type => {
            const value = params.get(type);
            if (value) {
                this.activeFilters[type] = value.split(',').filter(v => v.trim());
                hasFilters = true;
            }
        });

        return hasFilters;
    }
}