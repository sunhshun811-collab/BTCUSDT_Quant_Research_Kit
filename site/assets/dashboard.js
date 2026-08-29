
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

  $("#status").innerHTML=[
    ["Official phase",state.phase||"PHASE2_LOW_TURNOVER"],
    ["Visible data",`${summary.visible_start||"—"} → ${summary.visible_end||"—"}`],
    ["Base cost",`${fmt(summary.base_cost_bps_one_way,1)} bps / side`],
    ["Funding",yes(summary.funding_included)?"Included":"Not included"],
    ["Test start",summary.test_start||"—"],
    ["Run",(state.latest_run_id||manifest.run_id||"—")]
  ].map(x=>`<div class="statusLine"><span>${esc(x[0])}</span><b>${esc(x[1])}</b></div>`).join("");

  const cards=[
    ["Alphas",lb.length,"Official Phase2"],
    ["Candidates",candidates,"Screening pass"],
    ["Best Val Sharpe",fmt(best.val_net_sharpe_daily),"Net of configured cost"],
    ["Best Val Return",retVals.length?pct(Math.max(...retVals)):"—","Validation"],
    ["Median Ann. Turnover",fmt(median(lb.map(r=>r.val_annualized_turnover)),1),"Validation"],
    ["Best Gross bps / Turnover",grossVals.length?fmt(Math.max(...grossVals),2):"—","Execution efficiency"]
  ];
  $("#cards").innerHTML=cards.map(x=>`<div class="panel card"><div class="k">${esc(x[0])}</div><div class="v">${esc(x[1])}</div><div class="hint">${esc(x[2])}</div></div>`).join("");

  const columns=[
    ["alpha_id","Alpha"],["family","Family"],["hypothesis","Hypothesis"],
    ["train_net_sharpe_daily","Train Sharpe"],["val_net_sharpe_daily","Val Sharpe"],
    ["val_net_return","Val Return"],["val_max_drawdown","Val MDD"],
    ["val_ic_15m","IC 15m"],["val_ic_60m","IC 60m"],["val_ic_240m","IC 240m"],
    ["val_annualized_turnover","Ann. Turnover"],["val_gross_bps_per_unit_turnover","Gross bps/TO"],
    ["rebalance_minutes","Rebal m"],["phase2_candidate","Status"]
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
      if(k==="phase2_candidate") return `<td><span class="pill ${yes(v)?"pass":"research"}">${yes(v)?"PASS":"RESEARCH"}</span></td>`;
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
      showTip(e,`<b>${esc(r.alpha_id)}</b><br>${esc(r.family)}<br><span style="color:#92a4b8">${esc(r.hypothesis)}</span><br><br>Rebalance ${fmt(r.rebalance_minutes,0)}m · Half-life ${fmt(r.smoothing_halflife_minutes,0)}m · Band ${fmt(r.no_trade_band,2)}`);
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
    if(!pts.length){el.innerHTML="<div class='sectionSub'>No data</div>";return}
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
  scatter($("#trainVal"),lb,"train_net_sharpe_daily","val_net_sharpe_daily","Train Sharpe","Validation Sharpe");
  scatter($("#turnover"),lb,"val_annualized_turnover","val_net_sharpe_daily","Annualized Turnover","Validation Sharpe");

  function barTop(){
    const el=$("#sharpeBar"),W=700,H=280,P={l:160,r:30,t:8,b:18};
    const top=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,10);
    const vals=top.map(r=>num(r.val_net_sharpe_daily)).filter(v=>v!=null);
    if(!vals.length){el.innerHTML="No data";return}
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
    if(!costs.length||!vals.length){el.innerHTML="No data";return}
    const W=1100,H=280,P={l:50,r:185,t:14,b:34},xmin=Math.min(...costs),xmax=Math.max(...costs),ymin=Math.min(0,...vals),ymax=Math.max(0,...vals),X=x=>P.l+(x-xmin)/(xmax-xmin||1)*(W-P.l-P.r),Y=y=>H-P.b-(y-ymin)/(ymax-ymin||1)*(H-P.t-P.b);
    let s=`<svg viewBox="0 0 ${W} ${H}"><line x1="${P.l}" y1="${Y(0)}" x2="${W-P.r}" y2="${Y(0)}" stroke="#92a4b8"/>`;
    ids.forEach((id,i)=>{const rr=rows.filter(r=>r.alpha_id===id).sort((a,b)=>(num(a.cost_bps_one_way)??0)-(num(b.cost_bps_one_way)??0)),fam=(lb.find(x=>x.alpha_id===id)||{}).family,col=familyColor(fam),pts=rr.map(r=>`${X(num(r.cost_bps_one_way))},${Y(num(r.net_sharpe_daily))}`).join(" ");s+=`<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/>`;rr.forEach(r=>s+=`<circle cx="${X(num(r.cost_bps_one_way))}" cy="${Y(num(r.net_sharpe_daily))}" r="3" fill="${col}"/>`);s+=`<text x="${W-P.r+12}" y="${20+i*19}" fill="${col}" font-size="8">${esc(id)}</text>`});
    costs.forEach(c=>s+=`<text x="${X(c)}" y="${H-7}" fill="#92a4b8" text-anchor="middle" font-size="8">${c} bps</text>`);
    el.innerHTML=s+"</svg>";
  }
  costChart();

  function yearHeat(){
    const el=$("#yearHeat"),ids=[...lb].sort((a,b)=>(num(b.val_net_sharpe_daily)??-1e99)-(num(a.val_net_sharpe_daily)??-1e99)).slice(0,10).map(r=>r.alpha_id),rows=yearly.filter(r=>ids.includes(r.alpha_id)),years=[...new Set(rows.map(r=>num(r.year)).filter(v=>v!=null))].sort((a,b)=>a-b);
    if(!years.length){el.innerHTML="No data";return}
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
  $("#familiesGrid").innerHTML=fams.map(f=>`<div class="panel family"><h3>${esc(f.family)}</h3><div class="mline"><span>Alphas</span><b>${f.count}</b></div><div class="mline"><span>Candidates</span><b>${f.candidates}</b></div><div class="mline"><span>Best Alpha</span><b>${esc(f.bestAlpha)}</b></div><div class="mline"><span>Best Val Sharpe</span><b>${fmt(f.bestSharpe)}</b></div><div class="mline"><span>Avg Val Sharpe</span><b>${fmt(f.avgSharpe)}</b></div><div class="mline"><span>Median Turnover</span><b>${fmt(f.avgTurn,1)}</b></div></div>`).join("");

  const runs=[...(D.runs||[])].filter(r=>!String(r.phase||"").toUpperCase().includes("PHASE1")).reverse();
  const rcols=[["run_id","Run"],["phase","Phase"],["created_at_utc","UTC"],["alphas_researched","Alphas"],["candidate_count","Candidates"],["test_locked","Test Locked"]];
  $("#runsTable").innerHTML="<thead><tr>"+rcols.map(x=>`<th>${x[1]}</th>`).join("")+"</tr></thead><tbody>"+(runs.length?runs.map(r=>"<tr>"+rcols.map(([k])=>`<td>${k==="test_locked"?(yes(r[k])?"YES":"NO"):esc(r[k]??"—")}</td>`).join("")+"</tr>").join(""):`<tr><td colspan="${rcols.length}" style="text-align:left;color:#92a4b8">当前仅有一个正式 Phase2 基线；后续运行会自动追加。</td></tr>`)+"</tbody>";

  $("#footer").textContent=`Official policy: ${D.officialPolicy} · GitHub-built visualization · ${state.updated_at_utc||manifest.created_at_utc||""}`;
})().catch(err=>{
  document.body.innerHTML=`<pre style="padding:30px;color:#ff7d86;background:#080c12">Dashboard load failed:\n${String(err.stack||err)}</pre>`;
});
