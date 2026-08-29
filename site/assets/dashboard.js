(async function(){
  const D=await fetch("site-data.json",{cache:"no-store"}).then(r=>{
    if(!r.ok) throw new Error("site-data.json "+r.status);
    return r.json();
  });
  const $=s=>document.querySelector(s);
  const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
  const fmt=(v,d=2)=>num(v)==null?"—":num(v).toFixed(d);
  const pct=(v,d=1)=>num(v)==null?"—":(num(v)*100).toFixed(d)+"%";
  const yes=v=>v===true||v===1||String(v).toLowerCase()==="true";
  const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
  const BJ_TZ="Asia/Shanghai",BJ_OFFSET_MS=8*60*60*1000;
  const bjFmt=new Intl.DateTimeFormat("zh-CN",{timeZone:BJ_TZ,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
  const bjShortFmt=new Intl.DateTimeFormat("zh-CN",{timeZone:BJ_TZ,month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false});
  const bjTime=v=>{if(v==null||v==="")return"—";const d=new Date(typeof v==="number"?v:String(v));return Number.isNaN(d.getTime())?String(v):bjFmt.format(d).replaceAll("/","-");};
  const bjShort=v=>{const d=new Date(typeof v==="number"?v:String(v));return Number.isNaN(d.getTime())?"—":bjShortFmt.format(d);};
  const bjMonthBounds=month=>{const [y,m]=month.split("-").map(Number);return[Date.UTC(y,m-1,1)-BJ_OFFSET_MS,Date.UTC(y,m,1)-BJ_OFFSET_MS];};
  const familyColor=f=>{let h=0;for(const c of String(f))h=(h*31+c.charCodeAt(0))%360;return `hsl(${h} 58% 60%)`;};
  const tip=$("#tip");
  const showTip=(e,html)=>{tip.innerHTML=html;tip.style.display="block";tip.style.left=(e.clientX+12)+"px";tip.style.top=(e.clientY+12)+"px"};
  const hideTip=()=>tip.style.display="none";

  const lb=[...(D.leaderboard||[])];
  const cost=[...(D.costSensitivity||[])];
  const yearly=[...(D.yearly||[])];
  const summary=D.summary||{}, state=D.state||{}, manifest=D.manifest||{};
  const best=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99))[0]||{};
  const candidates=lb.filter(r=>yes(r.phase2_candidate)).length;
  const median=a=>{const x=a.map(num).filter(v=>v!=null).sort((a,b)=>a-b);if(!x.length)return null;const m=Math.floor(x.length/2);return x.length%2?x[m]:(x[m-1]+x[m])/2};
  const retVals=lb.map(r=>num(r.val_net_return)).filter(v=>v!=null);
  const grossVals=lb.map(r=>num(r.val_gross_bps_per_unit_turnover)).filter(v=>v!=null);
  const pkg=D.packageInfo||{};

  $("#status").innerHTML=[
    ["正式阶段",state.phase||"PHASE2_LOW_TURNOVER"],
    ["可见数据（北京时间）",`${bjTime(summary.visible_start)} → ${bjTime(summary.visible_end)}`],
    ["基础成本",`${fmt(summary.base_cost_bps_one_way,1)} bps / 单边`],
    ["Funding",yes(summary.funding_included)?"已纳入":"未纳入"],
    ["测试集起点（北京时间）",bjTime(summary.test_start)],
    ["Run",(state.latest_run_id||manifest.run_id||"—")]
  ].map(x=>`<div class="statusLine"><span>${esc(x[0])}</span><b>${esc(x[1])}</b></div>`).join("");

  const cards=[
    ["Alpha 数量",lb.length,"正式 Phase2"],
    ["原 Phase2 候选",candidates,"旧筛选标准，仅保留作历史对照"],
    ["最佳验证 Sharpe",fmt(best.val_net_sharpe_daily),"已扣除配置成本"],
    ["最佳验证收益",retVals.length?pct(Math.max(...retVals)):"—","验证集"],
    ["年化换手中位数",fmt(median(lb.map(r=>r.val_annualized_turnover)),1),"验证集"],
    ["最佳每换手毛收益",grossVals.length?fmt(Math.max(...grossVals),2):"—","执行效率"]
  ];
  $("#cards").innerHTML=cards.map(x=>`<div class="panel card"><div class="k">${esc(x[0])}</div><div class="v">${esc(x[1])}</div><div class="hint">${esc(x[2])}</div></div>`).join("");

  const pkgVersion=encodeURIComponent(pkg.sha256||state.content_hash||manifest.content_hash||"latest");
  const pkgHref=`downloads/research_package_latest.zip?v=${pkgVersion}`;
  ["analysisPackageTop","analysisPackageBottom"].forEach(id=>{
    const a=$("#"+id);
    if(a){a.href=pkgHref;}
  });
  const pkgSize=pkg.size_mb!=null?`${fmt(pkg.size_mb,2)} MB`:"—";
  const pkgFiles=pkg.file_count!=null?`${pkg.file_count} 个文件`:"—";
  const pkgRun=pkg.latest_run_id||state.latest_run_id||manifest.run_id||"—";
  if($("#analysisPackageMeta")) $("#analysisPackageMeta").textContent=`最新 Run：${pkgRun} · ${pkgSize}`;
  if($("#analysisPackageDetail")) $("#analysisPackageDetail").textContent=`最新 Run：${pkgRun} · ${pkgSize} · ${pkgFiles} · 生成：${bjTime(pkg.created_at_utc)} · SHA256 ${String(pkg.sha256||"—").slice(0,16)}…`;


  const columns=[
    ["alpha_id","Alpha"],["family","Family"],["direction_type_train","方向类型"],
    ["val_net_sharpe_daily","原 Val Sharpe"],["fixed_val_net_sharpe_daily","固定10%x10 Val Sharpe"],
    ["fixed_val_net_return","固定模型 Val收益"],["fixed_val_beta_btc_daily","BTC Beta"],
    ["fixed_val_beta_eth_daily","ETH Beta"],["fixed_val_residual_sharpe_daily","Residual Sharpe"],
    ["fixed_val_worst_price_mae","最坏价格MAE"],["fixed_val_worst_margin_equity_mae","最坏10x保证金MAE"],
    ["fixed_val_min_margin_remaining_fraction","最小保证金剩余"],["fixed_val_10x_danger_trades","危险交易"],
    ["phase2_candidate","原Phase2状态"]
  ];
  let sortKey="val_net_sharpe_daily",sortAsc=false;
  function renderLeaderboard(){
    const q=$("#search").value.toLowerCase(),f=$("#familyFilter").value,c=$("#candidateFilter").value;
    let rows=lb.filter(r=>{
      const hay=`${r.alpha_id} ${r.family} ${r.hypothesis}`.toLowerCase();
      return (!q||hay.includes(q))&&(!f||r.family===f)&&(!c||String(yes(r.phase2_candidate))===c);
    });
    rows.sort((a,b)=>{
      const xn=num(a[sortKey]),yn=num(b[sortKey]);
      if(xn!=null||yn!=null){
        const x=xn??-1e99,y=yn??-1e99;
        return sortAsc?x-y:y-x;
      }
      return sortAsc?String(a[sortKey]??"").localeCompare(String(b[sortKey]??"")):String(b[sortKey]??"").localeCompare(String(a[sortKey]??""));
    });
    const th="<thead><tr>"+columns.map(([k,n])=>`<th data-k="${k}">${esc(n)}${sortKey===k?(sortAsc?" ▲":" ▼"):""}</th>`).join("")+"</tr></thead>";
    const body="<tbody>"+rows.map(r=>`<tr class="${yes(r.phase2_candidate)?"candidate":""}" data-id="${esc(r.alpha_id)}">`+columns.map(([k])=>{
      const v=r[k];
      if(k==="phase2_candidate") return `<td><span class="pill ${yes(v)?"pass":"research"}">${yes(v)?"原Phase2候选":"原Phase2研究"}</span></td>`;
      if(k==="direction_type_train") return `<td>${esc(directionCn(v))}</td>`;
      if(k==="fixed_val_net_return"||k.includes("mae")||k==="fixed_val_min_margin_remaining_fraction") return `<td>${pct(v,2)}</td>`;
      if(k==="fixed_val_10x_danger_trades") return `<td class="${Number(v)>0?"riskDanger":"riskOk"}">${fmt(v,0)}</td>`;
      if(k==="val_net_return"||k==="val_max_drawdown") return `<td>${pct(v)}</td>`;
      if(k.includes("sharpe")||k.includes("beta_")||k.includes("ic_")||k==="val_gross_bps_per_unit_turnover") return `<td>${fmt(v,k.includes("ic_")?4:2)}</td>`;
      if(k==="val_annualized_turnover") return `<td>${fmt(v,1)}</td>`;
      return `<td title="${esc(v)}">${esc(v)}</td>`;
    }).join("")+"</tr>").join("")+"</tbody>";
    $("#leaderboardTable").innerHTML=th+body;
    document.querySelectorAll("#leaderboardTable th").forEach(th=>th.onclick=()=>{
      const k=th.dataset.k;
      if(sortKey===k) sortAsc=!sortAsc; else {sortKey=k;sortAsc=false}
      renderLeaderboard();
    });
    document.querySelectorAll("#leaderboardTable tbody tr").forEach(tr=>tr.onclick=e=>{
      const r=lb.find(x=>String(x.alpha_id)===tr.dataset.id);
      if(!r)return;
      showTip(e,`<b>${esc(r.alpha_id)}</b><br>${esc(r.family)} · ${esc(directionCn(r.direction_type_train))}<br><span style="color:#92a4b8">${esc(r.hypothesis)}</span><br><br>固定模型：10%逐仓保证金 × 10x · BTC Beta ${fmt(r.fixed_val_beta_btc_daily,3)} · Residual Sharpe ${fmt(r.fixed_val_residual_sharpe_daily,2)} · 最坏价格MAE ${pct(r.fixed_val_worst_price_mae,2)}`);
      setTimeout(hideTip,4500);
    });
  }
  [...new Set(lb.map(r=>r.family).filter(Boolean))].sort().forEach(f=>$("#familyFilter").insertAdjacentHTML("beforeend",`<option>${esc(f)}</option>`));
  $("#search").addEventListener("input",renderLeaderboard);
  $("#familyFilter").addEventListener("change",renderLeaderboard);
  $("#candidateFilter").addEventListener("change",renderLeaderboard);
  renderLeaderboard();

  function scatter(el,data,xk,yk,xlab,ylab){
    const W=700,H=280,P={l:55,r:18,t:14,b:34};
    const pts=data.map(d=>({d,x:num(d[xk]),y:num(d[yk])})).filter(p=>p.x!=null&&p.y!=null);
    if(!pts.length){el.innerHTML="<div class='sectionSub'>暂无数据</div>";return}
    let xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
    if(xmin===xmax){xmin-=1;xmax+=1} if(ymin===ymax){ymin-=1;ymax+=1}
    const X=x=>P.l+(x-xmin)/(xmax-xmin)*(W-P.l-P.r),Y=y=>H-P.b-(y-ymin)/(ymax-ymin)*(H-P.t-P.b);
    let s=`<svg viewBox="0 0 ${W} ${H}">`;
    for(let i=0;i<=4;i++){const y=P.t+i*(H-P.t-P.b)/4;s+=`<line x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}" stroke="#263445"/>`}
    s+=`<text x="${W/2}" y="${H-5}" fill="#92a4b8" text-anchor="middle" font-size="9">${esc(xlab)}</text>`;
    s+=`<text transform="translate(12 ${H/2}) rotate(-90)" fill="#92a4b8" text-anchor="middle" font-size="9">${esc(ylab)}</text>`;
    pts.forEach(p=>{const c=familyColor(p.d.family);s+=`<circle class="dot" data-id="${esc(p.d.alpha_id)}" cx="${X(p.x)}" cy="${Y(p.y)}" r="${yes(p.d.phase2_candidate)?5.5:3.8}" fill="${c}" fill-opacity=".86" stroke="${yes(p.d.phase2_candidate)?"#edf3f8":"none"}"/>`});
    s+="</svg>";el.innerHTML=s;
    el.querySelectorAll(".dot").forEach(dot=>{
      dot.onmousemove=e=>{const r=lb.find(x=>String(x.alpha_id)===dot.dataset.id);showTip(e,`<b>${esc(r.alpha_id)}</b><br>${esc(r.family)}<br>${esc(xlab)} ${fmt(r[xk],2)}<br>${esc(ylab)} ${fmt(r[yk],2)}`)};
      dot.onmouseleave=hideTip;
    });
  }
  scatter($("#trainVal"),lb,"train_net_sharpe_daily","val_net_sharpe_daily","训练 Sharpe","验证 Sharpe");
  scatter($("#turnover"),lb,"val_annualized_turnover","val_net_sharpe_daily","年化换手","验证 Sharpe");

  function barTop(){
    const el=$("#sharpeBar"),W=700,H=280,P={l:160,r:30,t:8,b:18};
    const top=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,10);
    const vals=top.map(r=>num(r.val_net_sharpe_daily)).filter(v=>v!=null);
    if(!vals.length){el.innerHTML="暂无数据";return}
    const mn=Math.min(0,...vals),mx=Math.max(0,...vals),X=v=>P.l+(v-mn)/(mx-mn||1)*(W-P.l-P.r),zero=X(0),bh=(H-P.t-P.b)/top.length;
    let s=`<svg viewBox="0 0 ${W} ${H}"><line x1="${zero}" y1="${P.t}" x2="${zero}" y2="${H-P.b}" stroke="#92a4b8"/>`;
    top.forEach((r,i)=>{const v=num(r.val_net_sharpe_daily)??0,y=P.t+i*bh+3,x=Math.min(zero,X(v)),w=Math.abs(X(v)-zero);s+=`<text x="${P.l-7}" y="${y+bh*.55}" fill="#d5dee7" text-anchor="end" font-size="8">${esc(r.alpha_id)}</text><rect x="${x}" y="${y}" width="${Math.max(w,1)}" height="${bh-6}" rx="3" fill="${familyColor(r.family)}"/><text x="${v>=0?X(v)+4:X(v)-4}" y="${y+bh*.55}" fill="#edf3f8" text-anchor="${v>=0?"start":"end"}" font-size="8">${fmt(v,2)}</text>`});
    el.innerHTML=s+"</svg>";
  }
  barTop();

  function icHeat(){
    const el=$("#icHeat"),top=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,12),cols=[["val_ic_15m","15m"],["val_ic_60m","60m"],["val_ic_240m","240m"]];
    const W=700,H=280,L=185,T=26,cw=(W-L-20)/3,rh=(H-T-8)/(top.length||1),vals=[];
    top.forEach(r=>cols.forEach(([k])=>{const v=num(r[k]);if(v!=null)vals.push(Math.abs(v))}));
    const cap=Math.max(...vals,0.001),color=v=>{if(v==null)return"#17202a";const a=Math.min(Math.abs(v)/cap,1),c=v>=0?"105,214,151":"255,125,134";return`rgba(${c},${.14+.8*a})`};
    let s=`<svg viewBox="0 0 ${W} ${H}">`;cols.forEach(([,n],j)=>s+=`<text x="${L+j*cw+cw/2}" y="15" fill="#92a4b8" text-anchor="middle" font-size="9">${n}</text>`);
    top.forEach((r,i)=>{s+=`<text x="${L-7}" y="${T+i*rh+rh*.64}" fill="#d5dee7" text-anchor="end" font-size="8">${esc(r.alpha_id)}</text>`;cols.forEach(([k],j)=>{const v=num(r[k]);s+=`<rect x="${L+j*cw+2}" y="${T+i*rh+2}" width="${cw-4}" height="${rh-4}" rx="3" fill="${color(v)}"/><text x="${L+j*cw+cw/2}" y="${T+i*rh+rh*.64}" fill="#edf3f8" text-anchor="middle" font-size="8">${fmt(v,4)}</text>`})});
    el.innerHTML=s+"</svg>";
  }
  icHeat();

  function costChart(){
    const el=$("#costChart"),ids=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,6).map(r=>r.alpha_id);
    const rows=cost.filter(r=>String(r.segment).toLowerCase()==="validation"&&ids.includes(r.alpha_id));
    const costs=[...new Set(rows.map(r=>num(r.cost_bps_one_way)).filter(v=>v!=null))].sort((a,b)=>a-b),vals=rows.map(r=>num(r.net_sharpe_daily)).filter(v=>v!=null);
    if(!costs.length||!vals.length){el.innerHTML="暂无数据";return}
    const W=1100,H=280,P={l:50,r:185,t:14,b:34},xmin=Math.min(...costs),xmax=Math.max(...costs),ymin=Math.min(0,...vals),ymax=Math.max(0,...vals),X=x=>P.l+(x-xmin)/(xmax-xmin||1)*(W-P.l-P.r),Y=y=>H-P.b-(y-ymin)/(ymax-ymin||1)*(H-P.t-P.b);
    let s=`<svg viewBox="0 0 ${W} ${H}"><line x1="${P.l}" y1="${Y(0)}" x2="${W-P.r}" y2="${Y(0)}" stroke="#92a4b8"/>`;
    ids.forEach((id,i)=>{const rr=rows.filter(r=>r.alpha_id===id).sort((a,b)=>(num(a.cost_bps_one_way)??0)-(num(b.cost_bps_one_way)??0)),fam=(lb.find(x=>x.alpha_id===id)||{}).family,col=familyColor(fam),pts=rr.map(r=>`${X(num(r.cost_bps_one_way))},${Y(num(r.net_sharpe_daily))}`).join(" ");s+=`<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/>`;rr.forEach(r=>s+=`<circle cx="${X(num(r.cost_bps_one_way))}" cy="${Y(num(r.net_sharpe_daily))}" r="3" fill="${col}"/>`);s+=`<text x="${W-P.r+12}" y="${20+i*19}" fill="${col}" font-size="8">${esc(id)}</text>`});
    costs.forEach(c=>s+=`<text x="${X(c)}" y="${H-7}" fill="#92a4b8" text-anchor="middle" font-size="8">${c} bps</text>`);
    el.innerHTML=s+"</svg>";
  }
  costChart();

  function yearHeat(){
    const el=$("#yearHeat"),ids=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,10).map(r=>r.alpha_id),rows=yearly.filter(r=>ids.includes(r.alpha_id)),years=[...new Set(rows.map(r=>num(r.year)).filter(v=>v!=null))].sort((a,b)=>a-b);
    if(!years.length){el.innerHTML="暂无数据";return}
    const W=1100,H=280,L=190,T=27,cw=(W-L-20)/years.length,rh=(H-T-8)/(ids.length||1),vals=rows.map(r=>Math.abs(num(r.net_return)??0)),cap=Math.max(...vals,0.01),color=v=>{if(v==null)return"#17202a";const a=Math.min(Math.abs(v)/cap,1),c=v>=0?"105,214,151":"255,125,134";return`rgba(${c},${.14+.8*a})`};
    let s=`<svg viewBox="0 0 ${W} ${H}">`;years.forEach((y,j)=>s+=`<text x="${L+j*cw+cw/2}" y="15" fill="#92a4b8" text-anchor="middle" font-size="8">${y}</text>`);
    ids.forEach((id,i)=>{s+=`<text x="${L-7}" y="${T+i*rh+rh*.64}" fill="#d5dee7" text-anchor="end" font-size="8">${esc(id)}</text>`;years.forEach((y,j)=>{const r=rows.find(x=>x.alpha_id===id&&num(x.year)===y),v=r?num(r.net_return):null;s+=`<rect x="${L+j*cw+2}" y="${T+i*rh+2}" width="${cw-4}" height="${rh-4}" rx="3" fill="${color(v)}"/><text x="${L+j*cw+cw/2}" y="${T+i*rh+rh*.64}" fill="#edf3f8" text-anchor="middle" font-size="7">${v==null?"—":pct(v,0)}</text>`})});
    el.innerHTML=s+"</svg>";
  }
  yearHeat();

  const famMap={};
  lb.forEach(r=>{const f=r.family||"Unknown";if(!famMap[f])famMap[f]=[];famMap[f].push(r)});
  const fams=Object.entries(famMap).map(([family,rows])=>{
    const val=rows.map(r=>num(r.val_net_sharpe_daily)).filter(v=>v!=null);
    const best=[...rows].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99))[0]||{};
    return {family,count:rows.length,candidates:rows.filter(r=>yes(r.phase2_candidate)).length,bestAlpha:best.alpha_id||"—",bestSharpe:num(best.val_net_sharpe_daily),avgSharpe:val.length?val.reduce((a,b)=>a+b,0)/val.length:null,avgTurn:median(rows.map(r=>r.val_annualized_turnover))};
  }).sort((a,b)=>(b.bestSharpe??-1e99)-(a.bestSharpe??-1e99));
  $("#familiesGrid").innerHTML=fams.map(f=>`<div class="panel family"><h3>${esc(f.family)}</h3><div class="mline"><span>Alpha 数</span><b>${f.count}</b></div><div class="mline"><span>候选数</span><b>${f.candidates}</b></div><div class="mline"><span>最佳 Alpha</span><b>${esc(f.bestAlpha)}</b></div><div class="mline"><span>最佳验证 Sharpe</span><b>${fmt(f.bestSharpe)}</b></div><div class="mline"><span>平均验证 Sharpe</span><b>${fmt(f.avgSharpe)}</b></div><div class="mline"><span>换手中位数</span><b>${fmt(f.avgTurn,1)}</b></div></div>`).join("");

  const runs=[...(D.runs||[])].filter(r=>!String(r.phase||"").toUpperCase().includes("PHASE1")).reverse();
  const rcols=[["run_id","Run"],["phase","阶段"],["created_at_utc","北京时间"],["alphas_researched","Alpha 数"],["candidate_count","原Phase2候选数"],["test_locked","测试集锁定"]];
  $("#runsTable").innerHTML="<thead><tr>"+rcols.map(x=>`<th>${x[1]}</th>`).join("")+"</tr></thead><tbody>"+(runs.length?runs.map(r=>"<tr>"+rcols.map(([k])=>`<td>${k==="test_locked"?(yes(r[k])?"是":"否"):k==="created_at_utc"?esc(bjTime(r[k])):esc(r[k]??"—")}</td>`).join("")+"</tr>").join(""):`<tr><td colspan="${rcols.length}" style="text-align:left;color:#92a4b8">当前仅有一个正式 Phase2 基线；后续运行会自动追加。</td></tr>`)+"</tbody>";


  // ---- Existing-factor fixed 10% margin x 10x replay / Beta / risk ----
  const fdiag=[...(D.factorDiagnostics||[])],betaProfile=[...(D.betaProfile||[])],replayIndex=D.replayIndex||{},available=D.availableFiles||{};
  document.querySelectorAll("[data-requires]").forEach(a=>{if(!available[a.dataset.requires])a.style.display="none"});
  const replayAlpha=$("#replayAlpha"),replayMonth=$("#replayMonth"),replaySide=$("#replaySide");
  let currentFactorReplay=null,currentMarket=null,currentSignals=[],currentResolution=15,selectedTrade=null;
  let viewStartMs=null,viewEndMs=null,dragging=false,dragX=0,dragStartA=0,dragStartB=0;
  function diagFor(id){return fdiag.find(x=>String(x.alpha_id)===String(id))||{}}
  function riskText(v){return v==="DANGER"?"危险":v==="WARNING"?"警告":v==="OK"?"正常":v||"—"}
  function sideCn(s){return s==="LONG"?"多头":s==="SHORT"?"空头":s||"—"}
  function directionCn(s){return ({LONG_ONLY:"多头因子",SHORT_ONLY:"空头因子",LONG_SHORT:"多空双向",ASYMMETRIC_LS:"非对称多空",UNRESOLVED:"未定型"})[s]||s||"—"}
  function actionCn(a){return ({OPEN_LONG:"开多",CLOSE_LONG:"平多",OPEN_SHORT:"开空",CLOSE_SHORT:"平空"})[a]||a}
  async function fetchJson(path){const r=await fetch(path,{cache:"no-store"});if(!r.ok)throw new Error(path+" "+r.status);return r.json()}
  async function fetchGzip(path){const r=await fetch(path,{cache:"no-store"});if(!r.ok)throw new Error(path+" "+r.status);const raw=await r.arrayBuffer();if(typeof DecompressionStream==="undefined")throw new Error("当前浏览器不支持 gzip 交易回放解压，请使用最新版 Edge / Chrome");const ds=new DecompressionStream("gzip"),stream=new Blob([raw]).stream().pipeThrough(ds);return new Response(stream).arrayBuffer()}
  function parseMarket1m(buf){const v=new DataView(buf),rows=[];if(v.byteLength<16)return rows;const start=Number(v.getBigInt64(0,true)),count=v.getInt32(8,true);let prevClose=0,o=16;for(let i=0;i<count&&o+16<=v.byteLength;i++,o+=16){const oo=prevClose+v.getInt32(o,true),hh=prevClose+v.getInt32(o+4,true),ll=prevClose+v.getInt32(o+8,true),cc=prevClose+v.getInt32(o+12,true);rows.push([start+i*60000,oo/100,hh/100,ll/100,cc/100]);prevClose=cc}return rows}
  function parseSignals(buf){const v=new DataView(buf),rows=[];for(let o=0;o+20<=v.byteLength;o+=20)rows.push([v.getFloat64(o,true),v.getFloat32(o+8,true),v.getFloat32(o+12,true),v.getFloat32(o+16,true)]);return rows}
  function monthsBetween(a,b){const out=[],d=new Date(a+BJ_OFFSET_MS),e=new Date(b+BJ_OFFSET_MS);let y=d.getUTCFullYear(),m=d.getUTCMonth(),ey=e.getUTCFullYear(),em=e.getUTCMonth();while(y<ey||(y===ey&&m<=em)){out.push(`${y}-${String(m+1).padStart(2,"0")}`);m++;if(m===12){m=0;y++}}return out}
  function fillReplaySelectors(){const alphas=replayIndex.alphas||[];if(!alphas.length){$("#replayNotice").textContent="当前 Run 尚未生成新的固定10%×10x交易回放数据。重新运行现有因子分析后才会出现；不会新增 Alpha。";[replayAlpha,replayMonth,replaySide].forEach(x=>x.disabled=true);return false}
    replayAlpha.innerHTML=alphas.map(a=>`<option value="${esc(a.alpha_id)}">${esc(a.alpha_id)} · ${esc(directionCn(a.direction_type_train))}</option>`).join("");replayMonth.innerHTML=(replayIndex.months||[]).map(m=>`<option value="${esc(m)}">${esc(m)}（北京时间）</option>`).join("");if(replayIndex.months?.length)replayMonth.value=replayIndex.months[replayIndex.months.length-1];
    $("#replayNotice").textContent="固定模型：单 Alpha · 10%逐仓保证金 · 10x杠杆 · 同方向不加减仓。信号只用 t-1 及以前信息，交易在 t 分钟 Open 执行。10x强平风险为 High/Low 压力代理，不冒充 Binance 精确强平价。";return true}
  function renderReplayStats(){const id=replayAlpha.value,d=diagFor(id),f=currentFactorReplay||{};const cards=[["方向类型",directionCn(f.direction_type_train||d.direction_type_train)],["主导方向",sideCn(f.dominant_side_train||d.dominant_side_train)],["Val 固定模型 Sharpe",fmt(lb.find(x=>x.alpha_id===id)?.fixed_val_net_sharpe_daily,2)],["Val BTC Beta",fmt(f.beta?.validation_btc??d.combined_val_beta_btc_daily,3)],["Val ETH Beta",fmt(f.beta?.validation_eth??d.combined_val_beta_eth_daily,3)],["Val Residual Sharpe",fmt(f.beta?.validation_residual_sharpe??d.combined_val_residual_sharpe_daily,2)],["最坏价格 MAE",pct(d.val_risk_worst_price_mae,2)],["最坏10x保证金 MAE",pct(d.val_risk_worst_margin_equity_mae,2)],["最小保证金剩余",pct(d.val_risk_min_margin_remaining_fraction,2)]];$("#replayStats").innerHTML=cards.map(x=>`<div class="replayStat"><div class="rk">${esc(x[0])}</div><div class="rv">${esc(x[1])}</div></div>`).join("")}
  function renderBetaTable(){const id=replayAlpha.value,rows=betaProfile.filter(x=>x.alpha_id===id&&x.segment==="validation");const cols=["基准","窗口","均值","标准差","P05","P95"];$("#replayBetaTable").innerHTML="<thead><tr>"+cols.map(x=>`<th>${x}</th>`).join("")+"</tr></thead><tbody>"+(rows.length?rows.map(r=>`<tr><td>${esc(r.benchmark)}</td><td>${esc(r.window_minutes)}m</td><td>${fmt(r.mean,3)}</td><td>${fmt(r.std,3)}</td><td>${fmt(r.p05,3)}</td><td>${fmt(r.p95,3)}</td></tr>`).join(""):"<tr><td colspan='6'>当前 Run 尚无 Rolling Beta Profile。</td></tr>")+"</tbody>"}
  function filteredEpisodes(){if(!currentFactorReplay)return[];const [a,b]=bjMonthBounds(replayMonth.value),side=replaySide.value;return(currentFactorReplay.episodes||[]).filter(e=>e.exit_time_ms>=a&&e.entry_time_ms<b&&(!side||e.side===side))}
  function filteredEvents(){if(!currentFactorReplay)return[];const side=replaySide.value;return(currentFactorReplay.events||[]).filter(e=>(!viewStartMs||e.timestamp_ms>=viewStartMs)&&(!viewEndMs||e.timestamp_ms<=viewEndMs)&&(!side||(side==="LONG"&&e.action.includes("LONG"))||(side==="SHORT"&&e.action.includes("SHORT"))))}
  function resetView(){const rows=currentMarket?.rows||[];if(rows.length){viewStartMs=rows[0][0];viewEndMs=rows[rows.length-1][0]+(currentResolution||1)*60000}}
  function visibleRows(){return(currentMarket?.rows||[]).filter(r=>r[0]>=viewStartMs&&r[0]<=viewEndMs)}
  function visibleSignals(){return(currentSignals||[]).filter(r=>r[0]>=viewStartMs&&r[0]<=viewEndMs)}
  function drawTri(ctx,x,y,up,color){ctx.fillStyle=color;ctx.beginPath();if(up){ctx.moveTo(x,y-7);ctx.lineTo(x-5,y+4);ctx.lineTo(x+5,y+4)}else{ctx.moveTo(x,y+7);ctx.lineTo(x-5,y-4);ctx.lineTo(x+5,y-4)}ctx.closePath();ctx.fill()}
  function drawReplay(cross=null){const canvas=$("#replayCanvas"),ctx=canvas.getContext("2d"),dpr=window.devicePixelRatio||1,w=Math.max(canvas.clientWidth,700),h=620;canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle="#091019";ctx.fillRect(0,0,w,h);const rows=visibleRows();if(!rows.length){ctx.fillStyle="#92a4b8";ctx.fillText("暂无K线数据",20,30);return}
    const L=62,R=18,T=18,B=30,priceH=390,signalTop=425,signalH=90,posTop=535,posH=55,pw=w-L-R;const tx=t=>L+(t-viewStartMs)/(viewEndMs-viewStartMs||1)*pw;const highs=rows.map(r=>+r[2]),lows=rows.map(r=>+r[3]);let lo=Math.min(...lows),hi=Math.max(...highs),pad=(hi-lo)*.04||1;lo-=pad;hi+=pad;const py=v=>T+(hi-v)/(hi-lo)*priceH;
    ctx.strokeStyle="#223042";ctx.lineWidth=1;ctx.font="9px system-ui";ctx.fillStyle="#92a4b8";for(let k=0;k<=5;k++){const y=T+k*priceH/5;ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(w-R,y);ctx.stroke();ctx.fillText((hi-k*(hi-lo)/5).toFixed(0),5,y+3)}
    for(const e of (currentFactorReplay?.episodes||[])){if(e.exit_time_ms<viewStartMs||e.entry_time_ms>viewEndMs)continue;if(replaySide.value&&e.side!==replaySide.value)continue;const x0=Math.max(L,tx(e.entry_time_ms)),x1=Math.min(w-R,tx(e.exit_time_ms));ctx.fillStyle=e.side==="LONG"?"rgba(105,214,151,.10)":"rgba(255,125,134,.10)";ctx.fillRect(x0,T,Math.max(1,x1-x0),priceH)}
    const cw=Math.max(1,Math.min(6,pw/Math.max(rows.length,1)*.7));for(const r of rows){const x=tx(r[0]),o=+r[1],hh=+r[2],ll=+r[3],c=+r[4],up=c>=o;ctx.strokeStyle=up?"#69d697":"#ff7d86";ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,py(hh));ctx.lineTo(x,py(ll));ctx.stroke();const y1=py(Math.max(o,c)),y2=py(Math.min(o,c));ctx.fillRect(x-cw/2,y1,cw,Math.max(1,y2-y1))}
    for(const e of filteredEvents()){const x=tx(e.timestamp_ms),y=py(+e.execution_price),a=e.action;if(x<L||x>w-R)continue;if(a==="OPEN_LONG")drawTri(ctx,x,y,true,"#69d697");else if(a==="CLOSE_LONG")drawTri(ctx,x,y,false,"#eac85f");else if(a==="OPEN_SHORT")drawTri(ctx,x,y,false,"#ff7d86");else if(a==="CLOSE_SHORT")drawTri(ctx,x,y,true,"#eac85f")}
    // signal panel: zscore and smoothed target
    ctx.strokeStyle="#263445";ctx.strokeRect(L,signalTop,pw,signalH);ctx.fillStyle="#92a4b8";ctx.fillText("标准化信号 / 平滑目标",5,signalTop+12);const sig=visibleSignals();const sy=v=>signalTop+signalH/2-Math.max(-3,Math.min(3,v))/3*(signalH*.42);ctx.strokeStyle="#69a7ff";ctx.beginPath();sig.forEach((r,i)=>{const x=tx(r[0]),y=sy(+r[1]);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.strokeStyle="#eac85f";ctx.beginPath();sig.forEach((r,i)=>{const x=tx(r[0]),y=sy(+r[2]*3);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.strokeStyle="#405064";ctx.beginPath();ctx.moveTo(L,sy(0));ctx.lineTo(w-R,sy(0));ctx.stroke();
    // fixed state panel
    ctx.strokeStyle="#263445";ctx.strokeRect(L,posTop,pw,posH);ctx.fillStyle="#92a4b8";ctx.fillText("固定仓位状态",5,posTop+12);const pY=v=>posTop+posH/2-v*(posH*.34);ctx.strokeStyle="#b8c7d8";ctx.beginPath();sig.forEach((r,i)=>{const x=tx(r[0]),y=pY(+r[3]);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.fillText("+1 多",L+3,posTop+10);ctx.fillText("0 空仓",L+3,posTop+posH/2+3);ctx.fillText("-1 空",L+3,posTop+posH-4);
    for(let k=0;k<=4;k++){const t=viewStartMs+k*(viewEndMs-viewStartMs)/4;ctx.fillStyle="#92a4b8";ctx.fillText(bjShort(t),tx(t)-24,h-8)}
    if(cross&&cross.x>=L&&cross.x<=w-R){ctx.strokeStyle="#718399";ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(cross.x,T);ctx.lineTo(cross.x,posTop+posH);ctx.stroke();ctx.setLineDash([])}
  }
  function nearestRowByTime(rows,t){let best=null,bd=Infinity;for(const r of rows){const d=Math.abs(r[0]-t);if(d<bd){bd=d;best=r}}return best}
  function canvasMouse(e){if(dragging)return;const c=$("#replayCanvas"),r=c.getBoundingClientRect(),x=e.clientX-r.left,w=r.width,L=62,R=18;if(x<L||x>w-R){$("#replayCrosshairInfo").style.display="none";drawReplay();return}const t=viewStartMs+(x-L)/(w-L-R)*(viewEndMs-viewStartMs),bar=nearestRowByTime(visibleRows(),t),sig=nearestRowByTime(visibleSignals(),t);drawReplay({x});const box=$("#replayCrosshairInfo");box.style.display="block";box.style.left=Math.min(x+12,w-230)+"px";box.style.top="18px";box.innerHTML=`<b>${bjTime(bar?.[0]??t)} 北京时间</b><br>O ${fmt(bar?.[1],2)} · H ${fmt(bar?.[2],2)} · L ${fmt(bar?.[3],2)} · C ${fmt(bar?.[4],2)}<br>z ${fmt(sig?.[1],3)} · 平滑 ${fmt(sig?.[2],3)} · 状态 ${fmt(sig?.[3],0)}`}
  async function loadMonth(){selectedTrade=null;currentResolution=replayIndex.overview_bar_minutes||15;$("#replayOverview").disabled=true;const id=replayAlpha.value,m=replayMonth.value;const sigPath=`replay/signals/${encodeURIComponent(id)}/${encodeURIComponent(m)}.bin.gz`;const [factor,market,sigBuf]=await Promise.all([fetchJson(`replay/factors/${encodeURIComponent(id)}.json`),fetchJson(`replay/market_${currentResolution}m/${encodeURIComponent(m)}.json`),fetchGzip(sigPath).catch(()=>new ArrayBuffer(0))]);currentFactorReplay=factor;currentMarket=market;currentSignals=parseSignals(sigBuf);resetView();renderReplayStats();renderBetaTable();drawReplay();renderReplayTrades()}
  async function loadTradeDetail(t){selectedTrade=t;const pad=60*60000,a=t.entry_time_ms-pad,b=t.exit_time_ms+pad,months=monthsBetween(a,b),id=replayAlpha.value;const mBufs=await Promise.all(months.map(m=>fetchGzip(`replay/market_1m/${m}.bin.gz`)));const sBufs=await Promise.all(months.map(m=>fetchGzip(`replay/signals/${encodeURIComponent(id)}/${m}.bin.gz`).catch(()=>new ArrayBuffer(0))));let rows=mBufs.flatMap(parseMarket1m).filter(r=>r[0]>=a&&r[0]<=b),sigs=sBufs.flatMap(parseSignals).filter(r=>r[0]>=a&&r[0]<=b);currentMarket={rows};currentSignals=sigs;currentResolution=1;viewStartMs=a;viewEndMs=b;$("#replayOverview").disabled=false;drawReplay();renderReplayTrades()}
  function renderReplayTrades(){const eps=filteredEpisodes().sort((a,b)=>a.entry_time_ms-b.entry_time_ms);const cols=["方向","开仓（北京时间）","平仓（北京时间）","持仓(分)","账户净收益","价格MAE","10x保证金MAE","账户MAE","MFE","最小保证金剩余","10x风险"];$("#replayTradesTable").innerHTML="<thead><tr>"+cols.map(c=>`<th>${c}</th>`).join("")+"</tr></thead><tbody>"+(eps.length?eps.map((e,i)=>`<tr data-i="${i}" class="${selectedTrade&&selectedTrade.episode_id===e.episode_id?"selected":""}"><td>${sideCn(e.side)}</td><td>${bjTime(e.entry_time_ms)}</td><td>${bjTime(e.exit_time_ms)}</td><td>${e.holding_minutes}</td><td>${pct(e.net_return_on_account,2)}</td><td>${pct(e.price_mae,2)}</td><td>${pct(e.margin_equity_mae,2)}</td><td>${pct(e.account_equity_mae,2)}</td><td>${pct(e.price_mfe,2)}</td><td>${pct(e.min_margin_remaining_fraction,2)}</td><td class="${e.risk_10x==="DANGER"?"riskDanger":e.risk_10x==="WARNING"?"riskWarning":"riskOk"}">${riskText(e.risk_10x)}</td></tr>`).join(""):"<tr><td colspan='11'>本月没有符合筛选条件的持仓区间。</td></tr>")+"</tbody>";document.querySelectorAll("#replayTradesTable tbody tr[data-i]").forEach(tr=>tr.onclick=()=>loadTradeDetail(eps[+tr.dataset.i]).catch(e=>{$("#replayNotice").textContent="1min明细加载失败："+(e.message||e)}))}
  function zoomCanvas(e){e.preventDefault();const c=e.currentTarget,r=c.getBoundingClientRect(),x=e.clientX-r.left,L=62,R=18;if(x<L||x>r.width-R)return;const center=viewStartMs+(x-L)/(r.width-L-R)*(viewEndMs-viewStartMs),factor=e.deltaY<0?.72:1.38,span=Math.max((currentResolution||1)*60000*20,Math.min((viewEndMs-viewStartMs)*factor,90*24*3600*1000));const frac=(center-viewStartMs)/(viewEndMs-viewStartMs);viewStartMs=center-span*frac;viewEndMs=viewStartMs+span;drawReplay()}
  function startDrag(e){dragging=true;dragX=e.clientX;dragStartA=viewStartMs;dragStartB=viewEndMs;e.currentTarget.style.cursor="grabbing"}
  function moveDrag(e){if(!dragging){canvasMouse(e);return}const c=e.currentTarget,r=c.getBoundingClientRect(),span=dragStartB-dragStartA,dt=-(e.clientX-dragX)/(r.width-80)*span;viewStartMs=dragStartA+dt;viewEndMs=dragStartB+dt;drawReplay()}
  function endDrag(e){dragging=false;e.currentTarget.style.cursor="crosshair"}
  if(fillReplaySelectors()){const c=$("#replayCanvas");replayAlpha.addEventListener("change",()=>loadMonth().catch(e=>{$("#replayNotice").textContent="回放加载失败："+(e.message||e)}));replayMonth.addEventListener("change",()=>loadMonth().catch(e=>{$("#replayNotice").textContent="回放加载失败："+(e.message||e)}));replaySide.addEventListener("change",()=>{drawReplay();renderReplayTrades()});$("#replayPrev").onclick=()=>{const a=replayIndex.months||[],i=a.indexOf(replayMonth.value);if(i>0){replayMonth.value=a[i-1];loadMonth()}};$("#replayNext").onclick=()=>{const a=replayIndex.months||[],i=a.indexOf(replayMonth.value);if(i>=0&&i<a.length-1){replayMonth.value=a[i+1];loadMonth()}};$("#replayOverview").onclick=()=>loadMonth();c.addEventListener("wheel",zoomCanvas,{passive:false});c.addEventListener("mousedown",startDrag);c.addEventListener("mousemove",moveDrag);window.addEventListener("mouseup",endDrag);c.addEventListener("mouseleave",e=>{if(!dragging){$("#replayCrosshairInfo").style.display="none";drawReplay()}});window.addEventListener("resize",()=>drawReplay());loadMonth().catch(e=>{$("#replayNotice").textContent="回放加载失败："+(e.message||e)})}

  $("#footer").textContent=`正式结果策略：${D.officialPolicy} · 页面由 GitHub 自动构建 · 更新时间（北京时间）：${bjTime(state.updated_at_utc||manifest.created_at_utc||pkg.created_at_utc)}`;
})().catch(err=>{
  document.body.innerHTML=`<pre style="padding:30px;color:#ff7d86;background:#080c12">Dashboard 加载失败：\n${String(err.stack||err)}</pre>`;
});
