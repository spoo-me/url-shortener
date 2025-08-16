async function authFetch(input, init){
    const opts = init || {};
    if(!opts.credentials){ opts.credentials = 'include'; }
    let res = await fetch(input, opts);
    if(res.status !== 401){ return res; }
    try{
        const refreshRes = await fetch('/auth/refresh', { method:'POST', credentials:'include' });
        if(!refreshRes.ok){ return res; }
        res = await fetch(input, opts);
        return res;
    }catch(e){
        return res;
    }
}

async function submitAuth(){
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    const user_name_input = document.getElementById('authUserName');
    const user_name = user_name_input ? user_name_input.value.trim() : '';
    const url = (typeof authMode !== 'undefined' && authMode === 'login') ? '/auth/login' : '/auth/register';
    const body = (typeof authMode !== 'undefined' && authMode === 'login') ? { email, password } : { email, password, user_name };
    try{
        const res = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body) });
        const data = await res.json().catch(() => ({}));
        if(!res.ok){ document.getElementById('authError').innerText = (data && data.error) || 'Something went wrong'; return; }
        closeAuthModal();
        window.location.href = '/dashboard';
    }catch(e){ document.getElementById('authError').innerText = 'Something went wrong'; }
}

async function logout(){
    try{
        const res = await fetch('/auth/logout', { method:'POST', credentials:'include' });
        await updateAuthNav();
        if(res.ok){ window.location.href = '/'; }
    }catch(e){ await updateAuthNav(); }
}

async function updateAuthNav(){
    try{
        const res = await authFetch('/auth/me', { credentials:'include' });
        const loggedIn = res.ok;
        let user = null;
        if(loggedIn){
            const data = await res.json().catch(() => ({}));
            user = data && data.user ? data.user : null;
        }
        const show = (id, visible, displayType='list-item') => { const el = document.getElementById(id); if(el){ el.style.display = visible ? displayType : 'none'; } };
        // Desktop
        show('nav-auth', !loggedIn);
        show('nav-profile', loggedIn);
        // Hide old direct links when logged in (now in dropdown)
        show('nav-dashboard', false);
        show('nav-keys', false);
        // Mobile
        show('m-nav-auth', !loggedIn);
        show('m-nav-dashboard', loggedIn);
        show('m-nav-keys', loggedIn);
        show('m-nav-logout', loggedIn);
        show('m-nav-profile', loggedIn, 'block');

        if(user){
            const username = (user.user_name && String(user.user_name).trim()) || (user.email ? String(user.email).split('@')[0] : 'user');
            const avatarUrl = `https://avatar.iran.liara.run/username?username=${encodeURIComponent(username)}`;
            const img = document.getElementById('profileAvatar'); if(img){ img.src = avatarUrl; img.alt = username; }
            const mimg = document.getElementById('mProfileAvatar'); if(mimg){ mimg.src = avatarUrl; mimg.alt = username; }
        }
    }catch(e){ /* default to logged out */ }
}

document.addEventListener('DOMContentLoaded', function(){
    if(typeof updateAuthNav === 'function'){
        updateAuthNav();
    }
});


