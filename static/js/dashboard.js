(function () {
	const root = document.getElementById('dashboard-root');
	if (!root) { return; }

	const rawHost = (root.getAttribute('data-host') || '');
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
		const statusChip = node.querySelector('.chip.status');
		const pw = node.querySelector('.chip.password');
		const mc = node.querySelector('.chip.max-clicks');
		const priv = node.querySelector('.chip.private-stats');
		const created = node.querySelector('.value.created');
		const last = node.querySelector('.value.last-click');
		const total = node.querySelector('.value.total-clicks');

		shortA.textContent = trimProtocol(displayHost) + (it.alias ? it.alias : '');
		shortA.href = '/' + (it.alias || '');
		long.textContent = it.long_url || '';
		long.title = it.long_url || '';

		statusChip.textContent = it.status || '—';
		statusChip.classList.add(String(it.status || '').toUpperCase());
		if (it.password_set) { pw.style.display = 'inline-flex'; }
		if (typeof it.max_clicks === 'number') { mc.style.display = 'inline-flex'; mc.textContent = `Max ${it.max_clicks}`; }
		if (it.private_stats) { priv.style.display = 'inline-flex'; }

		created.textContent = formatDate(it.created_at);
		last.textContent = formatTs(it.last_click);
		total.textContent = (it.total_clicks ?? '—');

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
				els.pagination.style.display = 'none';
				return;
			}
			const frag = document.createDocumentFragment();
			for (const it of data.items) { frag.appendChild(createItem(it)); }
			els.list.appendChild(frag);
			renderPagination();
		} catch (err) {
			clearList();
			els.empty.style.display = 'block';
		} finally {
			setLoading(false);
		}
	}

	function renderPagination() {
		const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
		if (totalPages <= 1) { els.pagination.style.display = 'none'; return; }
		els.pagination.style.display = 'flex';
		const start = (state.page - 1) * state.pageSize + 1;
		const end = Math.min(state.total, state.page * state.pageSize);
		els.pagination.innerHTML = '';
		const container = document.createElement('div');
		container.className = 'pager';
		const prev = document.createElement('button'); prev.className = 'btn'; prev.textContent = 'Prev'; prev.disabled = state.page <= 1;
		const next = document.createElement('button'); next.className = 'btn'; next.textContent = 'Next'; next.disabled = !state.hasNext;
		prev.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; fetchData(); } });
		next.addEventListener('click', () => { if (state.hasNext) { state.page += 1; fetchData(); } });
		container.appendChild(prev);
		container.appendChild(next);
		const info = document.createElement('div'); info.className = 'page-info'; info.textContent = `Showing ${start}-${end} of ${state.total}`;
		els.pagination.appendChild(container);
		els.pagination.appendChild(info);
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

	// initial load
	fetchData();
})();


