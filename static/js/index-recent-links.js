function handleCopyClick(a){const b=a.getAttribute("data-url"),c=document.createElement("input");c.value=b,document.body.appendChild(c),c.select(),c.setSelectionRange(0,99999),document.execCommand("copy"),document.body.removeChild(c),a.innerText="Copied!",setTimeout(()=>{a.innerText="Copy"},1e3)}function handleStatsClick(a){const b=a.parentNode.parentNode.parentNode.querySelector(".short-url a").getAttribute("href"),c=b.replace(/^\//,"");window.location.href=`/stats/${c}`}function handleEditClick(a){const b=a.getAttribute("data-alias");"function"==typeof openLandingEditModal&&openLandingEditModal(b)}document.addEventListener("click",a=>{a.target.classList.contains("copy-button")?handleCopyClick(a.target):a.target.classList.contains("stats-button")?handleStatsClick(a.target):a.target.classList.contains("edit-button")&&handleEditClick(a.target)});function renderRecentURLs(){const a=document.getElementById("recentURLs");if(!a)return;if(!0===window.isLoggedIn)return void(a.innerHTML="");let b=[];try{b=JSON.parse(localStorage.getItem("recentURLs"))||[]}catch(a){b=[]}a.innerHTML="",b.forEach(b=>{const c=`${window.location.origin}/${b}`,d=document.createElement("div");d.className="url-container",d.innerHTML=`
            <div class="section-1">
                <div class="left-section">
                    <span class="short-url">
                        <a href="/${b}" target="_blank">${c.replace(/^https?:\/\//,"")}</a>
                    </span>
                </div>
            </div>
            <div class="section-2">
                <div class="button-container">
                    <button class="copy-button" data-url="${c}">Copy</button>
                    <button class="edit-button" data-alias="${b}">Edit</button>
                    <button class="stats-button">Stats</button>
                </div>
            </div>
        `,a.appendChild(d)})}document.addEventListener("DOMContentLoaded",renderRecentURLs),document.addEventListener("auth:init",renderRecentURLs);