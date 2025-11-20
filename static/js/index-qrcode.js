function handleCopyClick(a){const b=a.getAttribute("data-url"),c=document.createElement("input");c.value=b,document.body.appendChild(c),c.select(),c.setSelectionRange(0,99999),document.execCommand("copy"),document.body.removeChild(c),a.innerText="Copied!",setTimeout(()=>{a.innerText="Copy"},1e3)}function handleStatsClick(a){const b=a.parentNode.parentNode.parentNode.querySelector(".short-url a").getAttribute("href"),c=b.replace(/^\//,"");window.location.href=`/stats/${c}`}document.addEventListener("click",a=>{a.target.classList.contains("copy-button")?handleCopyClick(a.target):a.target.classList.contains("stats-button")&&handleStatsClick(a.target)});function renderRecentURLs(){const a=document.getElementById("recentURLs");if(!a)return;let b=[];try{b=JSON.parse(localStorage.getItem("recentURLs"))||[]}catch(a){b=[]}a.innerHTML="",b.forEach(b=>{const c=`${window.location.origin}/${b}`,d=document.createElement("div");d.className="url-container",d.innerHTML=`
            <div class="section-1">
                <div class="left-section">
                    <span class="short-url">
                        <a href="/${b}" target="_blank">${c}</a>
                    </span>
                </div>
                <div class="right-section">
                    <div class="qr-code" data-url="${c}"></div>
                </div>
            </div>
            <div class="section-2">
                <div class="button-container">
                    <button class="copy-button" data-url="${c}">Copy</button>
                    <button class="stats-button">Stats</button>
                </div>
            </div>
        `,a.appendChild(d)});const c=a.querySelectorAll(".qr-code");c.forEach(a=>{const b=a.getAttribute("data-url"),c=new QRCode(a,{text:b,width:40,height:40,correctLevel:QRCode.CorrectLevel.L,margin:0,colorDark:"#000000",colorLight:"#ffffff"})})}document.addEventListener("DOMContentLoaded",renderRecentURLs);