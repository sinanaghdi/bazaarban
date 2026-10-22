(() => {
  const $ = id => document.getElementById(id);
  const fmt = new Intl.NumberFormat('fa-IR', {maximumFractionDigits:0});
  const fmtDecimal = new Intl.NumberFormat('fa-IR', {maximumFractionDigits:1});
  const money = value => fmt.format(Math.round(Number(value) || 0)) + ' ریال';
  const monthIntl = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {month:'short',year:'numeric',timeZone:'UTC'});
  const dateIntl = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'});
  const fromIso = s => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(s || ''))) return null;
    const d = new Date(s + 'T12:00:00Z');
    return Number.isNaN(d.getTime()) || d.toISOString().slice(0,10) !== s ? null : d;
  };
  const isValid = r => {
    const d = fromIso(String(r.sale_date || '')), q = Number(r.quantity), p = Number(r.unit_price_irr), disc = Number(r.discount_irr);
    return Boolean(d && String(r.invoice_id || '').trim() && String(r.store_id || '').trim() && String(r.store_name || '').trim() && String(r.product_code || '').trim() && String(r.product_name || '').trim() && Number.isFinite(q) && Number.isFinite(p) && Number.isFinite(disc) && p >= 0 && disc >= 0 && (q >= 0 || disc === 0));
  };
  const lineNet = r => Number(r.quantity) * Number(r.unit_price_irr) - Number(r.discount_irr);
  const setText = (id, value) => { $(id).textContent = value; };
  const escapeText = v => String(v).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  let rawRows = [];

  function buildQuality(rows) {
    const validCount = rows.filter(isValid).length;
    const fields = ['sale_date','invoice_id','store_id','store_name','product_code','product_name','customer_id','quantity','unit_price_irr','discount_irr'];
    const seen = new Set(); let dups = 0;
    rows.forEach(r => { const key = JSON.stringify(fields.map(k => r[k] == null ? '' : r[k])); if (seen.has(key)) dups++; else seen.add(key); });
    const missingCustomer = rows.filter(r => !String(r.customer_id == null ? '' : r.customer_id).trim()).length;
    const pct = rows.length ? validCount / rows.length * 100 : 0;
    setText('allRows', fmt.format(rows.length)); setText('invalidRows', fmt.format(rows.length-validCount));
    setText('duplicateRows', fmt.format(dups)); setText('missingCustomers', fmt.format(missingCustomer));
    setText('validPercent', fmtDecimal.format(pct) + '٪'); $('validProgress').style.width = pct + '%';
  }

  function calculate() {
    const start = $('startDate').value, end = $('endDate').value, store = $('storeFilter').value;
    let rows = rawRows.filter(isValid);
    if (start) rows = rows.filter(r => r.sale_date >= start);
    if (end) rows = rows.filter(r => r.sale_date <= end);
    if (store) rows = rows.filter(r => r.store_id === store);
    const positive = rows.filter(r => Number(r.quantity) > 0 && Number(r.unit_price_irr) > 0);
    const returns = rows.filter(r => Number(r.quantity) < 0);
    const invoices = new Set(positive.map(r => r.invoice_id));
    const gross = positive.reduce((s,r) => s + Number(r.quantity)*Number(r.unit_price_irr),0);
    const net = positive.reduce((s,r) => s + lineNet(r),0);
    const customers = new Map();
    positive.filter(r => String(r.customer_id || '').trim()).forEach(r => {
      const id = String(r.customer_id).trim();
      if (!customers.has(id)) customers.set(id,new Set());
      customers.get(id).add(r.invoice_id);
    });
    let repeat = 0; customers.forEach(v => { if (v.size >= 2) repeat++; });
    setText('grossSales', money(gross)); setText('positiveNet', money(net));
    setText('invoiceCount', fmt.format(invoices.size));
    setText('averageOrder', invoices.size ? money(net/invoices.size) : '—');
    setText('customerCount', fmt.format(customers.size));
    setText('repeatRate', customers.size ? fmtDecimal.format(repeat/customers.size*100)+'٪' : '—');
    const sortedDates = rows.map(r=>r.sale_date).sort();
    setText('activeRange', sortedDates.length ? dateIntl.format(fromIso(sortedDates[0])) + ' تا ' + dateIntl.format(fromIso(sortedDates[sortedDates.length-1])) : 'داده‌ای در این فیلتر نیست');
    drawTrend(rows); drawProducts(positive); drawStores(positive);
    void returns;
  }

  function drawTrend(rows) {
    const holder = $('trendChart');
    if (!rows.length) { holder.innerHTML = '<div class="empty">برای این فیلتر داده‌ای وجود ندارد.</div>'; return; }
    const months = new Map();
    rows.forEach(r => { const m=r.sale_date.slice(0,7); months.set(m,(months.get(m)||0)+lineNet(r)); });
    const vals = Array.from(months.entries()).sort((a,b)=>a[0].localeCompare(b[0]));
    let lo=Math.min(0,...vals.map(v=>v[1])), hi=Math.max(1,...vals.map(v=>v[1]));
    if (hi===lo) hi=lo+1;
    const width=760,height=208,left=24,right=18,top=18,bottom=30;
    const x=i=>left+i*((width-left-right)/Math.max(1,vals.length-1));
    const y=v=>top+(hi-v)/(hi-lo)*(height-top-bottom);
    const grid=[0,.25,.5,.75,1].map(f=>{
      const yy=top+f*(height-top-bottom), value=hi-f*(hi-lo);
      return '<line x1="'+left+'" y1="'+yy+'" x2="'+(width-right)+'" y2="'+yy+'" stroke="#edf2eb" stroke-dasharray="3 5"/><text x="'+(width-right)+'" y="'+(yy-4)+'" text-anchor="end" fill="#9aa69c" font-size="10">'+fmt.format(value/1000000)+' م</text>';
    }).join('');
    const points=vals.map((v,i)=>x(i)+','+y(v[1])).join(' ');
    const circles=vals.map((v,i)=>'<circle cx="'+x(i)+'" cy="'+y(v[1])+'" r="3.7" fill="#fff" stroke="#2a7a53" stroke-width="2"><title>'+monthIntl.format(new Date(v[0]+'-01T12:00:00Z'))+': '+money(v[1])+'</title></circle>').join('');
    const labels=vals.map((v,i)=>'<text x="'+x(i)+'" y="'+(height-7)+'" text-anchor="middle" fill="#718478" font-size="10">'+monthIntl.format(new Date(v[0]+'-01T12:00:00Z'))+'</text>').join('');
    holder.innerHTML='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="روند ماهانه بر اساس تاریخ میلادی" xmlns="http://www.w3.org/2000/svg">'+grid+'<polyline points="'+points+'" fill="none" stroke="#2a7a53" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'+circles+labels+'</svg>';
  }

  function drawProducts(rows) {
    const agg = new Map();
    rows.forEach(r => { const key=String(r.product_code||'')+'|'+String(r.product_name||''); const old=agg.get(key)||{name:r.product_name,net:0}; old.net+=lineNet(r); agg.set(key,old); });
    const top=Array.from(agg.values()).sort((a,b)=>b.net-a.net).slice(0,8), max=Math.max(1,...top.map(p=>p.net));
    $('productBars').innerHTML=top.length ? top.map(p=>'<div class="product-row"><span class="product-name" title="'+escapeText(p.name)+'">'+escapeText(p.name)+'</span><span class="bar-track"><i class="bar-fill" style="width:'+Math.max(0,p.net)/max*100+'%"></i></span><span class="bar-value">'+money(p.net)+'</span></div>').join('') : '<div class="empty">داده‌ای برای رتبه‌بندی وجود ندارد.</div>';
  }
  function drawStores(rows) {
    const agg=new Map();
    rows.forEach(r=>{ const id=r.store_id; const item=agg.get(id)||{name:r.store_name,sales:0,invoices:new Set()}; item.sales+=lineNet(r);item.invoices.add(r.invoice_id);agg.set(id,item); });
    const items=Array.from(agg.values()).sort((a,b)=>b.sales-a.sales);
    $('storeTable').innerHTML=items.length?items.map(s=>'<tr><td>'+escapeText(s.name)+'</td><td>'+money(s.sales)+'</td><td>'+fmt.format(s.invoices.size)+'</td></tr>').join(''):'<tr><td colspan="3">داده‌ای وجود ندارد.</td></tr>';
  }
  async function init() {
    try {
      const response=await fetch('../data/demo/sales_synthetic.json');
      if(!response.ok) throw new Error('dataset unavailable');
      rawRows=await response.json();
      const dates=rawRows.filter(isValid).map(r=>r.sale_date).sort();
      $('startDate').value=dates[0]||'';$('endDate').value=dates[dates.length-1]||'';
      const stores=new Map();rawRows.forEach(r=>{if(r.store_id&&r.store_name)stores.set(r.store_id,r.store_name);});
      Array.from(stores.entries()).sort((a,b)=>a[1].localeCompare(b[1],'fa')).forEach(pair=>{const opt=document.createElement('option');opt.value=pair[0];opt.textContent=pair[1];$('storeFilter').appendChild(opt);});
      buildQuality(rawRows);calculate();
      ['startDate','endDate','storeFilter'].forEach(id=>$(id).addEventListener('change',calculate));
      $('reset').addEventListener('click',()=>{$('startDate').value=dates[0]||'';$('endDate').value=dates[dates.length-1]||'';$('storeFilter').value='';calculate();});
    } catch (error) {
      document.querySelector('.content').insertAdjacentHTML('afterbegin','<div class="notice"><span>!</span><div><strong>فایل داده بارگذاری نشد.</strong><p>ابتدا python scripts/generate_demo_data.py را اجرا کنید و پروژه را از ریشه با python -m http.server 8000 اجرا کنید.</p></div></div>');
      console.error(error);
    }
  }
  init();
})();