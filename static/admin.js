(() => {
  if (window.__PAGE__ !== 'products') return;

  // === helpers ===
  const $ = (s) => document.querySelector(s);
  const rows = $('#rows'), empty = $('#empty');
  const q = $('#q'), brand = $('#brand'), quality = $('#quality'), sort = $('#sort');
  const prev = $('#prev'), next = $('#next'), pageLabel = $('#pageLabel'), pageSize = $('#pageSize');
  const dlg = $('#dlg'), frm = $('#frm'), saveBtn = $('#saveBtn'), btnAdd = $('#btn-add');

  const titleBrand = (slug) => {
    const s = (slug || '').trim();
    return s ? s[0].toUpperCase() + s.slice(1) : '—';
  };
  const toNumber = (x, d=0) => {
    const v = Number(x);
    return Number.isFinite(v) ? v : d;
  };

  // === state ===
  const state = {
    cache: [],       // полный список из /api/products
    page: 1,
    totalPages: 1,
  };

  // === API calls (ваш существующий бэкенд) ===
  const apiList = async () => {
    const r = await fetch('/api/products');
    if (!r.ok) throw new Error(await r.text());
    return r.json(); // массив
  };
  const apiCreate = async (payload) => {
    const r = await fetch('/api/products', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  };
  const apiUpdate = async (id, payload) => {
    const r = await fetch(`/api/products/${id}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  };
  const apiDelete = async (id) => {
    const r = await fetch(`/api/products/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  };

  // === client filtering/sorting/paging ===
  const applyFilters = () => {
    const term = (q.value || '').trim().toLowerCase();
    const brandSel = (brand.value || '').trim().toLowerCase();
    const qualitySel = (quality.value || '').trim().toLowerCase();
    let arr = [...state.cache];

    if (brandSel) arr = arr.filter(x => (x.brand || '').toLowerCase() === brandSel);
    if (qualitySel) arr = arr.filter(x => (x.quality || '').toLowerCase() === qualitySel);

    if (term) {
      arr = arr.filter(x => {
        const hay = [
          x.brand || '',
          x.model || '',
          x.quality || '',
          (x.tags || []).join(' '),
          x.type || '',
          x.vendor || '',
          x.specs || '',
        ].join(' ').toLowerCase();
        return hay.includes(term);
      });
    }

    switch (sort.value) {
      case 'price_asc':  arr.sort((a,b)=>toNumber(a.price)-toNumber(b.price)); break;
      case 'price_desc': arr.sort((a,b)=>toNumber(b.price)-toNumber(a.price)); break;
      case 'stock_asc':  arr.sort((a,b)=>toNumber(a.stock)-toNumber(b.stock)); break;
      case 'stock_desc': arr.sort((a,b)=>toNumber(b.stock)-toNumber(a.stock)); break;
      case 'model_asc':  arr.sort((a,b)=>String(a.model||'').localeCompare(String(b.model||''))); break;
      default:           arr.sort((a,b)=>toNumber(b.created_at)-toNumber(a.created_at)); // created_desc
    }
    return arr;
  };

  const render = () => {
    const filtered = applyFilters();
    const size = Number(pageSize.value) || 20;
    const total = filtered.length;
    state.totalPages = Math.max(1, Math.ceil(total/size));
    if (state.page > state.totalPages) state.page = state.totalPages;

    const start = (state.page-1)*size;
    const pageItems = filtered.slice(start, start+size);

    rows.innerHTML = '';
    for (const it of pageItems) {
      const tr = document.createElement('tr');
      const brandLabel = titleBrand(it.brand);
      const stockCell = (toNumber(it.stock) < 5)
        ? `<span class="badge warn">${toNumber(it.stock)}</span>`
        : toNumber(it.stock);

      const tags = (it.tags || []).join(', ');
      tr.innerHTML = `
        <td title="${it.id}">${String(it.id).slice(0,8)}…</td>
        <td>${brandLabel}</td>
        <td>${it.model ?? '—'}</td>
        <td><span class="badge">${it.quality ?? '—'}</span></td>
        <td class="num">${toNumber(it.price).toLocaleString('ru-RU')}</td>
        <td class="num">${stockCell}</td>
        <td>${tags || '—'}</td>
        <td>
          <div class="row-actions">
            <button class="icon" data-act="edit" data-id="${it.id}" title="Редактировать">✏️</button>
            <button class="icon" data-act="del"  data-id="${it.id}" title="Удалить">🗑️</button>
          </div>
        </td>`;
      rows.appendChild(tr);
    }

    empty.hidden = pageItems.length > 0;
    $('#pageLabel').textContent = `${state.page} / ${state.totalPages}`;
  };

  const reload = async () => {
    const list = await apiList();       // массив
    // для совместимости: добавим created_at, если нет
    state.cache = list.map(x => ({...x, created_at: x.created_at ?? 0}));
    state.page = 1;
    render();
  };

  // === events ===
  for (const el of [q, brand, quality, sort, pageSize]) {
    el.addEventListener('input', () => { state.page = 1; render(); });
  }
  prev.addEventListener('click', () => { if (state.page>1){ state.page--; render(); } });
  next.addEventListener('click', () => { if (state.page<state.totalPages){ state.page++; render(); } });

  rows.addEventListener('click', async (e) => {
    const btn = e.target.closest('button.icon'); if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    const current = state.cache.find(x => String(x.id) === String(id));

    if (act === 'edit') {
      // заполняем форму из кэша, т.к. GET /api/products/<id> у вас нет — и не нужно
      frm.brand.value   = current?.brand ?? '';
      frm.model.value   = current?.model ?? '';
      frm.quality.value = current?.quality ?? '';
      frm.price.value   = current?.price ?? '';
      frm.stock.value   = current?.stock ?? '';
      frm.currency.value= current?.currency ?? 'TJS';
      frm.vendor.value  = current?.vendor ?? '';
      frm.photo.value   = current?.photo ?? '';
      frm.type.value    = current?.type ?? '';
      frm.tags.value    = (current?.tags || []).join(',');
      frm.specs.value   = current?.specs ?? '';
      frm.active.value  = String(Boolean(current?.active ?? true));
      dlg.dataset.editId = id;
      $('#dlgTitle').textContent = `Редактировать`;
      dlg.showModal();

    } else if (act === 'del') {
      if (!confirm('Удалить товар?')) return;
      try {
        await apiDelete(id);
        await reload();
      } catch (err) {
        alert('Ошибка удаления: ' + err.message);
      }
    }
  });

  $('#btn-add').addEventListener('click', () => {
    frm.reset();
    frm.currency.value = 'TJS';
    frm.active.value = 'true';
    delete dlg.dataset.editId;
    $('#dlgTitle').textContent = 'Новый товар';
    dlg.showModal();
  });

  $('#saveBtn').addEventListener('click', async (e) => {
    e.preventDefault();
    const payload = {
      brand: (frm.brand.value || '').trim(),
      model: (frm.model.value || '').trim(),
      quality: (frm.quality.value || '').trim(),
      price: Number(frm.price.value || 0),
      stock: Number(frm.stock.value || 0),
      currency: (frm.currency.value || 'TJS').trim(),
      vendor: (frm.vendor.value || '').trim(),
      photo: (frm.photo.value || '').trim(),
      type: (frm.type.value || '').trim(),
      tags: (frm.tags.value || '').trim(),   // ваш API примет строку, сам распарсит
      specs: (frm.specs.value || '').trim(),
      active: frm.active.value === 'true',
    };
    if (!payload.model || !payload.quality) {
      alert('Укажите модель и качество'); return;
    }
    try {
      if (dlg.dataset.editId) {
        await apiUpdate(dlg.dataset.editId, payload);
      } else {
        await apiCreate(payload);
      }
      dlg.close();
      await reload();
    } catch (err) {
      alert('Ошибка сохранения: ' + err.message);
    }
  });

  // старт
  reload().catch(err => {
    console.error(err);
    alert('Ошибка загрузки /api/products');
  });
})();
