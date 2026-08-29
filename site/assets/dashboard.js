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
    ["可见数据",`${summary.visible_start||"—"} → ${summary.visible_end||"—"}`],
    ["基础成本",`${fmt(summary.base_cost_bps_one_way,1)} bps / 单边`],
    ["Funding",yes(summary.funding_included)?"已纳入":"未纳入"],
    ["测试集起点",summary.test_start||"—"],
    ["Run",(state.latest_run_id||manifest.run_id||"—")]
  ].map(x=>`<div class="statusLine"><span>${esc(x[0])}</span><b>${esc(x[1])}</b></div>`).join("");

  const cards=[
    ["Alpha 数量",lb.length,"正式 Phase2"],
    ["候选数量",candidates,"通过筛选"],
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
  if($("#analysisPackageDetail")) $("#analysisPackageDetail").textContent=`最新 Run：${pkgRun} · ${pkgSize} · ${pkgFiles} · SHA256 ${String(pkg.sha256||"—").slice(0,16)}…`;


  const columns=[
    ["alpha_id","Alpha"],["family","Family"],["hypothesis","研究假设"],
    ["train_net_sharpe_daily","训练 Sharpe"],["val_net_sharpe_daily","验证 Sharpe"],
    ["val_net_return","验证收益"],["val_max_drawdown","验证回撤"],
    ["val_ic_15m","IC 15m"],["val_ic_60m","IC 60m"],["val_ic_240m","IC 240m"],
    ["val_annualized_turnover","年化换手"],["val_gross_bps_per_unit_turnover","每换手毛收益"],
    ["rebalance_minutes","调仓(分)"],["phase2_candidate","状态"]
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
      if(k==="phase2_candidate") return `<td><span class="pill ${yes(v)?"pass":"research"}">${yes(v)?"通过":"研究"}</span></td>`;
      if(k==="val_net_return"||k==="val_max_drawdown") return `<td>${pct(v)}</td>`;
      if(k.includes("sharpe")||k.includes("ic_")||k==="val_gross_bps_per_unit_turnover") return `<td>${fmt(v,k.includes("ic_")?4:2)}</td>`;
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
      showTip(e,`<b>${esc(r.alpha_id)}</b><br>${esc(r.family)}<br><span style="color:#92a4b8">${esc(r.hypothesis)}</span><br><br>调仓 ${fmt(r.rebalance_minutes,0)} 分钟 · 半衰期 ${fmt(r.smoothing_halflife_minutes,0)} 分钟 · No-trade band ${fmt(r.no_trade_band,2)}`);
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
  const rcols=[["run_id","Run"],["phase","阶段"],["created_at_utc","UTC 时间"],["alphas_researched","Alpha 数"],["candidate_count","候选数"],["test_locked","测试集锁定"]];
  $("#runsTable").innerHTML="<thead><tr>"+rcols.map(x=>`<th>${x[1]}</th>`).join("")+"</tr></thead><tbody>"+(runs.length?runs.map(r=>"<tr>"+rcols.map(([k])=>`<td>${k==="test_locked"?(yes(r[k])?"是":"否"):esc(r[k]??"—")}</td>`).join("")+"</tr>").join(""):`<tr><td colspan="${rcols.length}" style="text-align:left;color:#92a4b8">当前仅有一个正式 Phase2 基线；后续运行会自动追加。</td></tr>`)+"</tbody>";


  // ---- Existing-factor trade replay / Beta / 10x risk ----
  const fdiag=[...(D.factorDiagnostics||[])];
  const replayIndex=D.replayIndex||{};
  const replayAlpha=$("#replayAlpha"), replayMonth=$("#replayMonth"), replaySide=$("#replaySide");
  let currentFactorReplay=null,currentMarket=null;

  function diagFor(id){return fdiag.find(x=>String(x.alpha_id)===String(id))||{}}
  function riskText(v){const x=String(v||"");return x==="DANGER"?"危险":x==="WARNING"?"警告":x==="OK"?"正常":x||"—"}
  function actionCn(a){return ({
    OPEN_LONG:"开多",CLOSE_LONG:"平多",OPEN_SHORT:"开空",CLOSE_SHORT:"平空",
    FLIP_TO_SHORT:"反手做空",FLIP_TO_LONG:"反手做多",ADD_LONG:"加多",REDUCE_LONG:"减多",
    ADD_SHORT:"加空",REDUCE_SHORT:"减空",POSITION_CHANGE:"调仓"
  })[a]||a}
  function sideCn(s){return s==="LONG"?"多头":s==="SHORT"?"空头":s||"—"}
  function directionCn(s){return ({LONG_ONLY:"多头因子",SHORT_ONLY:"空头因子",LONG_SHORT:"多空双向",ASYMMETRIC_LS:"非对称多空",UNRESOLVED:"未定型"})[s]||s||"—"}

  function fillReplaySelectors(){
    const alphas=(replayIndex.alphas||[]);
    if(!alphas.length){
      $("#replayNotice").textContent="当前正式结果还没有生成交易回放数据。安装分析升级后，重新运行一次现有 17 个因子即可生成；不会新增 Alpha。";
      replayAlpha.disabled=true;replayMonth.disabled=true;replaySide.disabled=true;
      return false;
    }
    replayAlpha.innerHTML=alphas.map(a=>`<option value="${esc(a.alpha_id)}">${esc(a.alpha_id)} · ${esc(directionCn(a.direction_type_train))}</option>`).join("");
    replayMonth.innerHTML=(replayIndex.months||[]).map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join("");
    if(replayIndex.months?.length) replayMonth.value=replayIndex.months[replayIndex.months.length-1];
    $("#replayNotice").textContent=`Test 仍锁定。K线显示 ${replayIndex.bar_minutes||15}min；交易轨迹按 1min 策略计算。10x 风险为不利价格波动代理，不等同于 Binance 精确强平价。`;
    return true;
  }

  async function fetchJson(path){
    const r=await fetch(path,{cache:"no-store"});
    if(!r.ok) throw new Error(path+" "+r.status);
    return r.json();
  }

  function renderReplayStats(){
    const id=replayAlpha.value,d=diagFor(id),f=currentFactorReplay||{};
    const cards=[
      ["方向类型",directionCn(f.direction_type_train||d.direction_type_train)],
      ["主导方向",sideCn(f.dominant_side_train||d.dominant_side_train)],
      ["Val BTC Beta",fmt(f.beta?.validation_btc??d.combined_val_beta_btc_daily,3)],
      ["Val ETH Beta",fmt(f.beta?.validation_eth??d.combined_val_beta_eth_daily,3)],
      ["Val Residual Sharpe",fmt(f.beta?.validation_residual_sharpe??d.combined_val_residual_sharpe_daily,2)],
      ["Val 多头 Sharpe",fmt(d.long_val_net_sharpe_daily,2)],
      ["Val 空头 Sharpe",fmt(d.short_val_net_sharpe_daily,2)]
    ];
    $("#replayStats").innerHTML=cards.map(x=>`<div class="replayStat"><div class="rk">${esc(x[0])}</div><div class="rv">${esc(x[1])}</div></div>`).join("");
  }

  function monthBounds(month){
    const [y,m]=month.split("-").map(Number);
    const start=Date.UTC(y,m-1,1),end=Date.UTC(y,m,1);
    return [start,end];
  }

  function filteredEpisodes(){
    if(!currentFactorReplay)return[];
    const [start,end]=monthBounds(replayMonth.value),side=replaySide.value;
    return (currentFactorReplay.episodes||[]).filter(e=>e.exit_time_ms>=start&&e.entry_time_ms<end&&(!side||e.side===side));
  }
  function filteredEvents(){
    if(!currentFactorReplay)return[];
    const [start,end]=monthBounds(replayMonth.value),side=replaySide.value;
    return (currentFactorReplay.events||[]).filter(e=>{
      if(e.timestamp_ms<start||e.timestamp_ms>=end)return false;
      if(!side)return true;
      const np=Number(e.new_position),pp=Number(e.prev_position);
      return side==="LONG"?(np>0||pp>0):(np<0||pp<0);
    });
  }

  function drawTriangle(ctx,x,y,up,color){
    ctx.fillStyle=color;ctx.beginPath();
    if(up){ctx.moveTo(x,y-6);ctx.lineTo(x-5,y+4);ctx.lineTo(x+5,y+4)}
    else{ctx.moveTo(x,y+6);ctx.lineTo(x-5,y-4);ctx.lineTo(x+5,y-4)}
    ctx.closePath();ctx.fill();
  }

  function drawReplay(){
    const canvas=$("#replayCanvas"),ctx=canvas.getContext("2d");
    const dpr=window.devicePixelRatio||1,w=Math.max(canvas.clientWidth,700),h=430;
    canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,w,h);ctx.fillStyle="#091019";ctx.fillRect(0,0,w,h);
    const rows=currentMarket?.rows||[];
    if(!rows.length){ctx.fillStyle="#92a4b8";ctx.fillText("暂无 K 线数据",20,30);return}

    const P={l:62,r:18,t:18,b:34},pw=w-P.l-P.r,ph=h-P.t-P.b;
    const lows=rows.map(r=>Number(r[3])),highs=rows.map(r=>Number(r[2]));
    let lo=Math.min(...lows),hi=Math.max(...highs);const pad=(hi-lo)*.04||1;lo-=pad;hi+=pad;
    const X=i=>P.l+(i+.5)/rows.length*pw,Y=v=>P.t+(hi-v)/(hi-lo)*ph;
    const tx=t=>{
      const t0=Number(rows[0][0]),t1=Number(rows[rows.length-1][0]);
      return P.l+(t-t0)/(t1-t0||1)*pw;
    };

    // Grid
    ctx.strokeStyle="#223042";ctx.lineWidth=1;ctx.font="9px system-ui";ctx.fillStyle="#92a4b8";
    for(let k=0;k<=5;k++){const y=P.t+k*ph/5;ctx.beginPath();ctx.moveTo(P.l,y);ctx.lineTo(w-P.r,y);ctx.stroke();const v=hi-k*(hi-lo)/5;ctx.fillText(v.toFixed(0),5,y+3)}

    // Holding intervals
    for(const e of filteredEpisodes()){
      const x0=Math.max(P.l,tx(e.entry_time_ms)),x1=Math.min(w-P.r,tx(e.exit_time_ms));
      ctx.fillStyle=e.side==="LONG"?"rgba(105,214,151,.11)":"rgba(255,125,134,.11)";
      ctx.fillRect(x0,P.t,Math.max(1,x1-x0),ph);
    }

    // Candles
    const cw=Math.max(1,Math.min(5,pw/rows.length*.7));
    rows.forEach((r,i)=>{
      const o=+r[1],hh=+r[2],ll=+r[3],c=+r[4],x=X(i),up=c>=o;
      ctx.strokeStyle=up?"#69d697":"#ff7d86";ctx.fillStyle=ctx.strokeStyle;
      ctx.beginPath();ctx.moveTo(x,Y(hh));ctx.lineTo(x,Y(ll));ctx.stroke();
      const y1=Y(Math.max(o,c)),y2=Y(Math.min(o,c));ctx.fillRect(x-cw/2,y1,cw,Math.max(1,y2-y1));
    });

    // Major trade markers; add/reduce are small dots.
    for(const e of filteredEvents()){
      const x=tx(e.timestamp_ms),y=Y(Number(e.price)),a=e.action;
      if(x<P.l||x>w-P.r)continue;
      if(a==="OPEN_LONG"||a==="FLIP_TO_LONG")drawTriangle(ctx,x,y,true,"#69d697");
      else if(a==="CLOSE_LONG")drawTriangle(ctx,x,y,false,"#eac85f");
      else if(a==="OPEN_SHORT"||a==="FLIP_TO_SHORT")drawTriangle(ctx,x,y,false,"#ff7d86");
      else if(a==="CLOSE_SHORT")drawTriangle(ctx,x,y,true,"#eac85f");
      else{ctx.fillStyle="#7aaaff";ctx.beginPath();ctx.arc(x,y,2.2,0,Math.PI*2);ctx.fill()}
    }

    // Month labels
    ctx.fillStyle="#92a4b8";ctx.font="9px system-ui";
    for(let k=0;k<=4;k++){const i=Math.min(rows.length-1,Math.floor(k*(rows.length-1)/4));const dt=new Date(rows[i][0]);ctx.fillText(`${dt.getUTCMonth()+1}/${dt.getUTCDate()}`,X(i)-12,h-10)}
  }

  function renderReplayTrades(){
    const eps=filteredEpisodes().sort((a,b)=>a.entry_time_ms-b.entry_time_ms);
    const cols=["方向","开仓","平仓","持仓(分)","净收益","MAE","MFE","持仓内最大回撤","10x风险"];
    $("#replayTradesTable").innerHTML="<thead><tr>"+cols.map(c=>`<th>${c}</th>`).join("")+"</tr></thead><tbody>"+
      (eps.length?eps.map(e=>`<tr><td>${sideCn(e.side)}</td><td>${esc(e.entry_time)}</td><td>${esc(e.exit_time)}</td><td>${esc(e.holding_minutes)}</td><td>${pct(e.net_return,2)}</td><td>${pct(e.mae,2)}</td><td>${pct(e.mfe,2)}</td><td>${pct(e.holding_max_drawdown,2)}</td><td><span class="pill ${e.risk_10x==="OK"?"pass":"research"}">${riskText(e.risk_10x)}</span></td></tr>`).join(""):"<tr><td colspan='9'>本月没有符合筛选条件的持仓区间。</td></tr>")+"</tbody>";
  }

  async function loadReplay(){
    if(!replayIndex.alphas?.length)return;
    try{
      const id=replayAlpha.value,month=replayMonth.value,bar=replayIndex.bar_minutes||15;
      [currentFactorReplay,currentMarket]=await Promise.all([
        fetchJson(`replay/factors/${encodeURIComponent(id)}.json`),
        fetchJson(`replay/market_${bar}m/${encodeURIComponent(month)}.json`)
      ]);
      renderReplayStats();drawReplay();renderReplayTrades();
    }catch(e){
      $("#replayNotice").textContent="回放数据加载失败："+String(e.message||e);
    }
  }

  if(fillReplaySelectors()){
    replayAlpha.addEventListener("change",loadReplay);replayMonth.addEventListener("change",loadReplay);replaySide.addEventListener("change",()=>{drawReplay();renderReplayTrades()});
    $("#replayPrev").onclick=()=>{const a=replayIndex.months||[],i=a.indexOf(replayMonth.value);if(i>0){replayMonth.value=a[i-1];loadReplay()}};
    $("#replayNext").onclick=()=>{const a=replayIndex.months||[],i=a.indexOf(replayMonth.value);if(i>=0&&i<a.length-1){replayMonth.value=a[i+1];loadReplay()}};
    window.addEventListener("resize",()=>{if(currentMarket)drawReplay()});
    loadReplay();
  }

  $("#footer").textContent=`正式结果策略：${D.officialPolicy} · 页面由 GitHub 构建 · ${state.updated_at_utc||manifest.created_at_utc||""}`;
})().catch(err=>{
  document.body.innerHTML=`<pre style="padding:30px;color:#ff7d86;background:#080c12">Dashboard 加载失败：\n${String(err.stack||err)}</pre>`;
});
