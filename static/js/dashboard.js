(function () {
	// Get host URL from window config or fallback to root element
	const rawHost = window.dashboardConfig?.hostUrl || document.querySelector('[data-host]')?.getAttribute('data-host') || '';
	const host = rawHost.replace(/\/+$/, '');
	const displayHost = host ? (host + '/') : '/';

	const els = {
		search: document.getElementById('f-search'),
		status: document.getElementById('f-status'),
		password: document.getElementById('f-password'),
		maxClicks: document.getElementById('f-maxclicks'),
		createdAfter: document.getElementById('f-created-after'),
		createdBefore: document.getElementById('f-created-before'),
		sortBy: document.getElementById('f-sortby'),
		order: document.getElementById('f-order'),
		pageSize: document.getElementById('f-pagesize'),
		apply: document.getElementById('btn-apply'),
		reset: document.getElementById('btn-reset'),
		optionsBtn: document.getElementById('btn-options'),
		optionsDropdown: document.getElementById('options-dropdown'),
		loading: document.getElementById('list-loading'),
		empty: document.getElementById('list-empty'),
		list: document.getElementById('links-list'),
		pagination: document.getElementById('pagination'),
		tpl: document.getElementById('tpl-link-item'),
	};

	let state = {
		page: 1,
		hasNext: false,
		total: 0,
		pageSize: 20,
		sortBy: 'created_at',
		sortOrder: 'descending',
		filters: {},
	};

	function toEpochSeconds(value) {
		if (!value) return undefined;
		try { return Math.floor(new Date(value).getTime() / 1000); } catch { return undefined; }
	}

	function buildQuery() {
		const filter = {};
		if (els.search.value.trim()) filter.search = els.search.value.trim();
		if (els.status.value) filter.status = els.status.value;
		if (els.password.value) filter.passwordSet = els.password.value;
		if (els.maxClicks.value) filter.maxClicksSet = els.maxClicks.value;
		if (els.createdAfter.value) filter.createdAfter = toEpochSeconds(els.createdAfter.value);
		if (els.createdBefore.value) filter.createdBefore = toEpochSeconds(els.createdBefore.value);

		const params = new URLSearchParams();
		params.set('page', String(state.page));
		params.set('pageSize', String(els.pageSize.value || state.pageSize));
		params.set('sortBy', els.sortBy.value || state.sortBy);
		params.set('sortOrder', els.order.value || state.sortOrder);
		if (Object.keys(filter).length) { params.set('filter', JSON.stringify(filter)); }
		return params.toString();
	}

	function setLoading(isLoading) {
		els.loading.style.display = isLoading ? 'block' : 'none';
	}

	function clearList() {
		els.list.innerHTML = '';
	}

	function formatDate(iso) {
		if (!iso) return '—';
		try {
			const d = new Date(iso);
			return d.toLocaleString();
		} catch { return '—'; }
	}

	function formatTs(ts) {
		if (!ts && ts !== 0) return '—';
		try {
			const d = new Date(ts * 1000);
			return d.toLocaleString();
		} catch { return '—'; }
	}

	function trimProtocol(url) {
		if (!url) return '';
		return String(url).replace(/^https?:\/\//i, '');
	}

	function createItem(it) {
		const node = els.tpl.content.firstElementChild.cloneNode(true);
		const shortA = node.querySelector('.link-short');
		const long = node.querySelector('.link-long');
		const activeBadge = node.querySelector('.badge-active');
		const inactiveBadge = node.querySelector('.badge-inactive');
		const pwBadge = node.querySelector('.badge-password');
		const mcBadge = node.querySelector('.badge-max-clicks');
		const privBadge = node.querySelector('.badge-private');
		const created = node.querySelector('.created-date');
		const last = node.querySelector('.last-click-date');
		const total = node.querySelector('.total-clicks-count');

		// Short URL
		shortA.textContent = trimProtocol(displayHost) + (it.alias ? it.alias : '');
		shortA.href = '/' + (it.alias || '');

		// Long URL
		long.textContent = it.long_url || '';
		long.title = it.long_url || '';

		// Dates and clicks
		created.textContent = formatDate(it.created_at);
		last.textContent = formatTs(it.last_click);
		total.textContent = (it.total_clicks ?? '0');

		// Status badges - show appropriate badge based on status
		if (it.status === 'ACTIVE') {
			activeBadge.style.display = 'inline-flex';
			inactiveBadge.style.display = 'none';
		} else if (it.status === 'INACTIVE') {
			activeBadge.style.display = 'none';
			inactiveBadge.style.display = 'inline-flex';
		} else {
			activeBadge.style.display = 'none';
			inactiveBadge.style.display = 'none';
		}

		// Password badge
		if (it.password_set) {
			pwBadge.style.display = 'inline-flex';
		}

		// Max clicks badge
		if (typeof it.max_clicks === 'number') {
			mcBadge.style.display = 'inline-flex';
			mcBadge.setAttribute('data-tooltip', `Max clicks: ${it.max_clicks}`);
		}

		// Private stats badge
		if (it.private_stats) {
			privBadge.style.display = 'inline-flex';
		}

		// Store full URL data on the row for the modal
		node.setAttribute('data-url-data', JSON.stringify(it));
		node.style.cursor = 'pointer';
		node.classList.add('clickable-row');

		return node;
	}

	async function fetchData() {
		setLoading(true);
		els.empty.style.display = 'none';
		try {
			const qs = buildQuery();
			const doFetch = (typeof window.authFetch === 'function') ? window.authFetch : fetch;
			const res = await doFetch(`/api/v1/urls?${qs}`, { credentials: 'include' });
			if (!res.ok) { throw new Error('Request failed'); }
			const data = await res.json();
			state.page = data.page;
			state.pageSize = data.pageSize;
			state.total = data.total;
			state.hasNext = data.hasNext;
			state.sortBy = data.sortBy;
			state.sortOrder = data.sortOrder;

			clearList();
			if (!data.items || data.items.length === 0) {
				els.empty.style.display = 'block';
				document.getElementById('links-table').style.display = 'none';
				els.pagination.style.display = 'none';
				return;
			}
			document.getElementById('links-table').style.display = 'block';
			const frag = document.createDocumentFragment();
			for (const it of data.items) { frag.appendChild(createItem(it)); }
			els.list.appendChild(frag);
			renderPagination();
			
			// Initialize tooltips for the newly created items
			initializeTooltips();
		} catch (err) {
			clearList();
			els.empty.style.display = 'block';
			document.getElementById('links-table').style.display = 'none';
		} finally {
			setLoading(false);
		}
	}

	// Initialize Tippy.js tooltips for attribute badges
	function initializeTooltips() {
		// Destroy existing tooltips first
		if (window.attributeTooltips) {
			window.attributeTooltips.forEach(instance => instance.destroy());
		}
		window.attributeTooltips = [];

		// Find all tooltip triggers and initialize Tippy.js
		const tooltipTriggers = document.querySelectorAll('.tooltip-trigger[data-tooltip]');
		
		tooltipTriggers.forEach(element => {
			// Remove the title attribute to prevent native tooltips
			element.removeAttribute('title');
			
			const instance = tippy(element, {
				content: element.getAttribute('data-tooltip'),
				placement: 'top',
				theme: 'dark',
				animation: 'fade',
				duration: [200, 150],
				delay: [200, 0],
				arrow: true,
				hideOnClick: false,
				trigger: 'mouseenter focus',
				zIndex: 9999
			});
			window.attributeTooltips.push(instance);
		});
	}

	function renderPagination() {
		const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
		if (totalPages <= 1) { els.pagination.style.display = 'none'; return; }
		els.pagination.style.display = 'flex';
		const start = (state.page - 1) * state.pageSize + 1;
		const end = Math.min(state.total, state.page * state.pageSize);
		els.pagination.innerHTML = '';
		const info = document.createElement('div');
		info.className = 'pagination-info';
		info.textContent = `Showing ${start} to ${end} of ${state.total}`;

		const container = document.createElement('div');
		container.className = 'pagination-controls';
		const prev = document.createElement('button'); prev.className = 'btn'; prev.textContent = 'Prev'; prev.disabled = state.page <= 1;
		const next = document.createElement('button'); next.className = 'btn'; next.textContent = 'Next'; next.disabled = !state.hasNext;
		prev.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; fetchData(); } });
		next.addEventListener('click', () => { if (state.hasNext) { state.page += 1; fetchData(); } });
		container.appendChild(prev);
		container.appendChild(next);

		els.pagination.appendChild(info);
		els.pagination.appendChild(container);
	}

	function applyFilters() {
		state.page = 1;
		fetchData();
	}

	function resetFilters() {
		for (const key of ['search', 'status', 'password', 'maxClicks', 'createdAfter', 'createdBefore']) {
			if (els[key]) els[key].value = '';
		}
		if (els.sortBy) els.sortBy.value = 'created_at';
		if (els.order) els.order.value = 'descending';
		// reset segmented visual state
		document.querySelectorAll('.seg').forEach(seg => {
			const targetId = seg.getAttribute('data-target');
			const hidden = document.getElementById(targetId);
			const defaultValue = (targetId === 'f-order') ? 'descending' : '';
			if (hidden) hidden.value = defaultValue;
			seg.setAttribute('data-active', (targetId === 'f-order') ? '0' : '2');
		});
		if (els.pageSize) els.pageSize.value = '20';
		applyFilters();
	}

	// wire events
	els.apply.addEventListener('click', applyFilters);
	els.reset.addEventListener('click', resetFilters);
	els.search.addEventListener('keydown', (e) => { if (e.key === 'Enter') { applyFilters(); } });

	// options dropdown toggle
	function toggleOptions() {
		if (!els.optionsDropdown) return;
		const isOpen = els.optionsDropdown.style.display !== 'none';
		els.optionsDropdown.style.display = isOpen ? 'none' : 'block';
	}
	if (els.optionsBtn) { els.optionsBtn.addEventListener('click', toggleOptions); }
	window.addEventListener('click', (e) => {
		if (!els.optionsDropdown) return;
		if (e.target === els.optionsBtn || els.optionsBtn.contains(e.target)) { return; }
		if (!els.optionsDropdown.contains(e.target)) { els.optionsDropdown.style.display = 'none'; }
	});

	// segmented controls behavior
	function initSegments() {
		const segs = document.querySelectorAll('.seg');
		segs.forEach(seg => {
			const targetId = seg.getAttribute('data-target');
			const hidden = document.getElementById(targetId);
			const buttons = Array.from(seg.querySelectorAll('button[data-value]'));
			const indexByValue = new Map(buttons.map((b, i) => [b.getAttribute('data-value'), i]));
			function apply(value) {
				if (hidden) { hidden.value = value; }
				const idx = indexByValue.has(value) ? indexByValue.get(value) : 0;
				seg.setAttribute('data-active', String(idx));
			}
			apply(hidden ? hidden.value : '');
			buttons.forEach(btn => btn.addEventListener('click', () => apply(btn.getAttribute('data-value') || '')));
		});
	}

	initSegments();

	// Expose fetchData globally for other components to refresh the list
	window.fetchData = fetchData;

	// initial load
	fetchData();
})();


