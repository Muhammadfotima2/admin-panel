(() => {
  if (!window.__PAGE__ || window.__PAGE__ !== 'products') return;

  const $ = s => document.querySelector(s);
  const rows = $('#rows');
  const empty = $('#empty');
  const q = $('#q'), brand = $('#brand'), quality = $('#quality'), sort = $('#sort');
  const prev = $('#prev'), next = $('#next'), pageLabel = $('#pageLabel'), pageSize = $('#pageSize');
  const dlg = $('#dlg'), frm = $('#frm'), saveBtn = $('#saveBtn'), btnAdd = $('#btn-add');

  let state = { page:1, totalPages:1, editingId:null };

  const fetchList = async () => {
    const params = new URLSearchParams({
      q: q.value.trim(),
      brand: brand.value,
      quality: quality.value,
      sort: sort.value,
      page: state.page,
      page_size: pageSize.value
    });
    const r = await fetch(`/api/products?${params}`);
    if (!r.ok){ console.error(await r.text()); return; }
    const data = await r.json();
    state.totalPages = data.total_pages;
    pageLabel.textContent = `${state.page} / ${state.totalPages}`;
    renderRows(data.items);
    empty.hidden = data.items.length > 0;
  };

  const currency = x => new Intl.NumberFormat('ru-RU', {maximumFractionDigits:2}).format(x);

  const renderRows = (items) => {
    rows.innerHTML = '';
    for (const it of items){
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${it.id}</td>
        <td>${it.brand}</td>
        <td>${it.model}</td>
        <td><span class="badge">${it.quality}</span></td>
        <td class="num">${currency(it.price)}</td>
        <td class="num">${it.stock < 5 ? `<span class="badge warn">${it.stock}</span>` : it.stock}</td>
        <td>
          <div class="row-actions">
            <button class="icon" data-act="edit" title="Редактировать" data-id="${it.id}">✏️</button>
            <button class="icon" data-act="del" title="Удалить" data-id="${it.id}">🗑️</button>
          </div>
        </td>`;
      rows.appendChild(tr);
    }
  };

  rows.addEventListener('click', async (e) => {
    const btn = e.target.closest('button.icon'); if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    if (act === 'edit'){
      const r = await fetch(`/api/products/${id}`);
      const it = await r.json();
      frm.brand.value = it.brand;
      frm.model.value = it.model;
      frm.quality.value = it.quality;
      frm.price.value = it.price;
      frm.stock.value = it.stock;
      state.editingId = it.id;
      $('#dlgTitle').textContent = `Редактировать #${id}`;
      dlg.showModal();
    } else if (act === 'del'){
      if (!confirm('Удалить товар?')) return;
      const r = await fetch(`/api/products/${id}`, {method:'DELETE'});
      if (r.ok){ fetchList(); }
      else alert(await r.text());
    }
  });

  btnAdd.addEventListener('click', () => {
    state.editingId = null;
    frm.reset();
    $('#dlgTitle').textContent = 'Новый товар';
    dlg.showModal();
  });

  saveBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const payload = {
      brand: frm.brand.value.trim(),
      model: frm.model.value.trim(),
      quality: frm.quality.value.trim(),
      price: parseFloat(frm.price.value),
      stock: parseInt(frm.stock.value, 10)
    };
    if (!payload.brand || !payload.model || !payload.quality){ alert('Заполните все поля'); return; }
    let r;
    if (state.editingId){
      r = await fetch(`/api/products/${state.editingId}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    } else {
      r = await fetch('/api/products', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    }
    if (r.ok){ dlg.close(); fetchList(); } else { alert(await r.text()); }
  });

  for (const el of [q, brand, quality, sort, pageSize]){
    el.addEventListener('input', () => { state.page = 1; fetchList(); });
  }
  prev.addEventListener('click', () => { if (state.page>1){ state.page--; fetchList(); } });
  next.addEventListener('click', () => { if (state.page<state.totalPages){ state.page++; fetchList(); } });

  fetchList();
})();
