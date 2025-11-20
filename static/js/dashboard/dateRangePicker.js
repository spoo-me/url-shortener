class DateRangePicker{constructor(a={}){this.options={container:a.container||"dateRangeContainer",onRangeChange:a.onRangeChange||(()=>{}),defaultRange:a.defaultRange||"last-7-days",...a},this.currentRange=this.options.defaultRange,this.customFromValue="now-7d",this.customToValue="now",this.history=[],this.init()}init(){this.loadHistory(),this.render(),this.setupEventListeners(),this.updateRelativeSelection()}updateRelativeSelection(){document.querySelectorAll(".relative-option").forEach(a=>{a.classList.toggle("selected",a.dataset.value===this.currentRange)})}render(){const a=document.getElementById(this.options.container);a&&(a.innerHTML=`
            <div class="date-range-picker">
                <div class="date-range-trigger" id="dateRangeTrigger">
                    <i class="ti ti-clock clock-icon"></i>
                    <span class="selected-range">${this.formatDisplayRange()}</span>
                    <i class="ti ti-chevron-down dropdown-icon"></i>
                </div>
                
                <div class="date-range-dropdown" id="dateRangeDropdown" style="display: none;">
                    <div class="dropdown-content">
                        <div class="content-layout">
                            <!-- Relative Section -->
                            <div class="relative-section">
                                <h3 class="section-title">Relative</h3>
                                <div class="relative-options">
                                    ${this.renderRelativeOptions()}
                                </div>
                            </div>
                            
                            <!-- Custom Section -->
                            <div class="custom-section">
                                <h3 class="section-title">Custom</h3>
                                <div class="custom-inputs">
                                    <div class="input-row">
                                        <div class="input-group">
                                            <label>From</label>
                                            <input type="text" id="customFrom" placeholder="now-7d" value="${this.customFromValue||"now-7d"}">
                                        </div>
                                        <div class="input-group">
                                            <label>To</label>
                                            <input type="text" id="customTo" placeholder="now" value="${this.customToValue||"now"}">
                                        </div>
                                    </div>
                                    <button class="apply-btn" id="applyCustomRange">Apply</button>
                                </div>
                                
                                <div class="history-section">
                                    <h4>History</h4>
                                    <div class="history-list" id="historyList">
                                        ${this.renderHistory()}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `)}renderRelativeOptions(){return[{value:"last-30-minutes",label:"Last 30 minutes"},{value:"last-60-minutes",label:"Last 60 minutes"},{value:"last-3-hours",label:"Last 3 hours"},{value:"last-6-hours",label:"Last 6 hours"},{value:"last-12-hours",label:"Last 12 hours"},{value:"last-24-hours",label:"Last 24 hours"},{value:"last-2-days",label:"Last 2 days"},{value:"last-7-days",label:"Last 7 days"},{value:"last-14-days",label:"Last 14 days"},{value:"last-30-days",label:"Last 30 days"},{value:"everything",label:"Everything"},{value:"custom",label:"Custom"}].map(a=>`
            <div class="relative-option ${this.currentRange===a.value?"selected":""}" 
                 data-value="${a.value}">
                ${a.label}
            </div>
        `).join("")}renderHistory(){return this.history.length?this.history.map(a=>`
            <div class="history-item" data-from="${a.from}" data-to="${a.to}">
                <i class="ti ti-clock-hour-3 history-icon"></i>
                <span>${a.display}</span>
            </div>
        `).join(""):"<div class=\"history-empty\">No recent selections</div>"}setupEventListeners(){const a=document.getElementById("dateRangeTrigger"),b=document.getElementById("dateRangeDropdown");a?.addEventListener("click",c=>{c.stopPropagation();const d="block"===b.style.display;"function"==typeof window.closeAllModals&&window.closeAllModals(window.dashboard),d||(b.style.display="block",a.classList.add("active"))}),document.addEventListener("click",c=>{c.target.closest(".date-range-picker")||(b.style.display="none",a.classList.remove("active"))}),document.querySelectorAll(".relative-option").forEach(a=>{a.addEventListener("click",()=>{this.selectRelativeRange(a.dataset.value)})}),document.getElementById("applyCustomRange")?.addEventListener("click",()=>{this.applyCustomRange()}),document.querySelectorAll(".history-item").forEach(a=>{a.addEventListener("click",()=>{this.selectHistoryItem(a.dataset.from,a.dataset.to)})});const c=document.getElementById("customFrom"),d=document.getElementById("customTo");c?.addEventListener("input",a=>{this.validateCustomInput(a.target)}),d?.addEventListener("input",a=>{this.validateCustomInput(a.target)})}selectRelativeRange(a){if("custom"===a){const a=document.getElementById("customFrom");return void(a&&a.focus())}this.currentRange=a,document.querySelectorAll(".relative-option").forEach(b=>{b.classList.toggle("selected",b.dataset.value===a)});const b=document.querySelector(".selected-range");b&&(b.textContent=this.formatDisplayRange()),document.getElementById("dateRangeDropdown").style.display="none",document.getElementById("dateRangeTrigger").classList.remove("active");const c=this.parseRelativeRange(a);this.options.onRangeChange(c)}applyCustomRange(){const a=document.getElementById("customFrom"),b=document.getElementById("customTo");if(!a||!b)return;const c=a.value.trim(),d=b.value.trim();if(!c||!d)return void this.showError("Both From and To fields are required");try{const a=this.parseCustomRange(c,d);this.addToHistory(c,d,`${c} - ${d}`),this.customFromValue=c,this.customToValue=d,this.currentRange="custom",this.updateRelativeSelection();const b=document.querySelector(".selected-range");b&&(b.textContent=`${c} - ${d}`),document.getElementById("dateRangeDropdown").style.display="none",document.getElementById("dateRangeTrigger").classList.remove("active"),this.options.onRangeChange(a)}catch(a){this.showError(a.message)}}parseRelativeRange(a){const b=new Date;let c;return c="last-30-minutes"===a?new Date(b.getTime()-1800000):"last-60-minutes"===a?new Date(b.getTime()-3600000):"last-3-hours"===a?new Date(b.getTime()-10800000):"last-6-hours"===a?new Date(b.getTime()-21600000):"last-12-hours"===a?new Date(b.getTime()-43200000):"last-24-hours"===a?new Date(b.getTime()-86400000):"last-2-days"===a?new Date(b.getTime()-172800000):"last-7-days"===a?new Date(b.getTime()-604800000):"last-14-days"===a?new Date(b.getTime()-1209600000):"last-30-days"===a?new Date(b.getTime()-2592000000):"everything"===a?new Date(b.getTime()-7776000000):new Date(b.getTime()-604800000),{start:c.toISOString(),end:b.toISOString(),range:a}}parseCustomRange(a,b){const c=this.parseCustomInput(a),d=this.parseCustomInput(b);if(c>=d)throw new Error("From date must be before To date");return{start:c.toISOString(),end:d.toISOString(),range:"custom"}}parseCustomInput(a){if(a=a.trim().toLowerCase(),"now"===a)return new Date;const b=a.match(/^now-(\d+)([dhm])$/);if(b){const a=parseInt(b[1]),c=b[2],d=new Date;switch(c){case"d":return new Date(d.getTime()-1e3*(60*(60*(24*a))));case"h":return new Date(d.getTime()-1e3*(60*(60*a)));case"m":return new Date(d.getTime()-1e3*(60*a));default:throw new Error(`Invalid time unit: ${c}`)}}const c=new Date(a);if(isNaN(c.getTime()))throw new Error(`Invalid date format: ${a}. Use formats like "now", "now-30d", "now-2h", "now-15m", "2024-01-01", etc.`);return c}validateCustomInput(a){try{this.parseCustomInput(a.value),a.classList.remove("invalid"),a.classList.add("valid")}catch(b){a.classList.remove("valid"),a.classList.add("invalid")}}formatDisplayRange(){const a={"last-30-minutes":"Last 30 minutes","last-60-minutes":"Last 60 minutes","last-3-hours":"Last 3 hours","last-6-hours":"Last 6 hours","last-12-hours":"Last 12 hours","last-24-hours":"Last 24 hours","last-2-days":"Last 2 days","last-7-days":"Last 7 days","last-14-days":"Last 14 days","last-30-days":"Last 30 days",everything:"Everything",custom:`${this.customFromValue||"now-7d"} - ${this.customToValue||"now"}`};return a[this.currentRange]||"Last 7 days"}addToHistory(a,b,c){const d={from:a,to:b,display:c,timestamp:Date.now()};this.history=this.history.filter(c=>c.from!==a||c.to!==b),this.history.unshift(d),this.history=this.history.slice(0,10),this.saveHistory(),this.updateHistoryUI()}loadHistory(){try{const a=localStorage.getItem("dateRangeHistory");if(a){const b=JSON.parse(a);this.history=0<b.length?b:this.getDefaultHistory()}else this.history=this.getDefaultHistory()}catch(a){console.warn("Failed to load date range history:",a),this.history=this.getDefaultHistory()}}getDefaultHistory(){return[{from:"now-7d",to:"now-3d",display:"now-7d - now-3d",timestamp:Date.now()-864e5},{from:"now-7d",to:"now-4d",display:"now-7d - now-4d",timestamp:Date.now()-1728e5},{from:"now-7d",to:"now-1d",display:"now-7d - now-1d",timestamp:Date.now()-2592e5},{from:"now-30d",to:"now-1d",display:"now-30d - now-1d",timestamp:Date.now()-3456e5},{from:"now-30d",to:"now-5d",display:"now-30d - now-5d",timestamp:Date.now()-432e6},{from:"now-30d",to:"now-10d",display:"now-30d - now-10d",timestamp:Date.now()-5184e5},{from:"now-30d",to:"now-20d",display:"now-30d - now-20d",timestamp:Date.now()-6048e5}]}saveHistory(){try{localStorage.setItem("dateRangeHistory",JSON.stringify(this.history))}catch(a){console.warn("Failed to save date range history:",a)}}updateHistoryUI(){const a=document.getElementById("historyList");a&&(a.innerHTML=this.renderHistory(),document.querySelectorAll(".history-item").forEach(a=>{a.addEventListener("click",()=>{this.selectHistoryItem(a.dataset.from,a.dataset.to)})}))}selectHistoryItem(a,b){document.getElementById("customFrom").value=a,document.getElementById("customTo").value=b,this.applyCustomRange()}showError(a){alert(a)}getCurrentRange(){return"custom"===this.currentRange?this.parseCustomRange(this.customFromValue,this.customToValue):this.parseRelativeRange(this.currentRange)}setRange(a){this.currentRange=a,this.render(),this.setupEventListeners(),this.updateRelativeSelection()}}window.DateRangePicker=DateRangePicker;