// Mobile-first calendar + CRUD de citas
(function(){
  const calendarEl = document.getElementById('calendar');
  const monthLabel = document.getElementById('month-label');
  const prevBtn = document.getElementById('prev-month');
  const nextBtn = document.getElementById('next-month');
  const btnNueva = document.getElementById('btn-nueva');
  const selectedDayLabel = document.getElementById('selected-day-label');
  const selectedDayCount = document.getElementById('selected-day-count');
  const selectedDayBody = document.getElementById('selected-day-body');

  const modal = document.getElementById('day-modal');
  const modalBody = document.getElementById('modal-body');
  const modalDate = document.getElementById('modal-date');
  const closeModal = document.getElementById('close-modal');
  const modalAdd = document.getElementById('modal-add');

  const formModal = document.getElementById('form-modal');
  const closeForm = document.getElementById('close-form');
  const form = document.getElementById('cita-form');
  const formTitle = document.getElementById('form-title');
  const deleteBtn = document.getElementById('delete-btn');

  const nombre = document.getElementById('nombre');
  const apellidos = document.getElementById('apellidos');
  const telefono = document.getElementById('telefono');
  const fecha = document.getElementById('fecha');
  const hora = document.getElementById('hora');
  const horaFin = document.getElementById('hora_fin');
  const tipoCitaTexto = document.getElementById('tipo_cita_texto');
  const tipoCitaSelect = document.getElementById('tipo_cita_select');
  const notas = document.getElementById('notas');
  const citaId = document.getElementById('cita-id');

  const state = {
    today: new Date(),
    year: new Date().getFullYear(),
    month: new Date().getMonth(),
    tipos: [],
    horario: null,
    citasMes: {},
    selectedDate: null,
    selectedDayData: [],
    horaFinManual: false
  };

  function formatMonthYear(year, month) {
    return new Date(year, month, 1).toLocaleString('es-ES', { month: 'long', year: 'numeric' });
  }

  function formatLongDate(year, month, day) {
    return new Date(year, month, day).toLocaleDateString('es-ES', {
      weekday:'long', day:'2-digit', month:'long', year:'numeric'
    });
  }

  function getSelectedDateParts(){
    if(!state.selectedDate) return null;
    const [year, month, day] = state.selectedDate.split('-').map(Number);
    return { year, month: month - 1, day };
  }

  function renderSelectedDayPanel(){
    if(!selectedDayBody || !selectedDayLabel || !selectedDayCount) return;
    const parts = getSelectedDateParts();
    if(!parts) return;

    selectedDayLabel.textContent = formatLongDate(parts.year, parts.month, parts.day);
    selectedDayCount.textContent = `${state.selectedDayData.length} cita${state.selectedDayData.length === 1 ? '' : 's'}`;

    if(state.isSunday && !(state.horario && state.horario.trabaja_domingo)){
      selectedDayCount.textContent = 'Cerrado';
      selectedDayBody.innerHTML = `
        <div class="agenda-day-empty">
          <span class="text-2xl">🚫</span>
          <p class="text-sm font-semibold text-gray-600">El consultorio no trabaja los domingos</p>
          <p class="text-xs text-gray-400">Horario laboral: Lun-Vie 14:00-18:00 · Sáb 09:00-13:00</p>
        </div>`;
      return;
    }

    if(!state.selectedDayData || state.selectedDayData.length === 0){
      selectedDayBody.innerHTML = `
        <div class="agenda-day-empty">
          <span class="text-2xl">📅</span>
          <p class="text-sm font-semibold text-gray-600">No hay citas para este día</p>
          <p class="text-xs text-gray-400">Cuando registres una nueva cita aparecerá aquí.</p>
        </div>`;
      return;
    }

    selectedDayBody.innerHTML = state.selectedDayData.map(c => `
      <article class="agenda-day-item">
        <div class="min-w-0">
          <div class="font-semibold text-gray-800 truncate">${c.paciente_completo}</div>
          <div class="text-xs text-primary/70 font-medium mt-0.5">${c.tipo}</div>
          <div class="text-xs text-gray-400 mt-1 truncate">${c.telefono || 'Sin teléfono'}</div>
        </div>
        <div class="agenda-day-time">${c.hora_formateada}</div>
      </article>`).join('');
  }

  async function loadSelectedDayData(year, month, day){
    const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    state.selectedDate = dateStr;

    const clickedDate = new Date(year, month, day);
    const todayDate = new Date(state.today.getFullYear(), state.today.getMonth(), state.today.getDate());
    state.isSunday = clickedDate.getDay() === 0;
    state.isPast = clickedDate < todayDate;

    if(state.isSunday && !(state.horario && state.horario.trabaja_domingo)){
      state.selectedDayData = [];
      renderSelectedDayPanel();
      return;
    }

    try {
      state.selectedDayData = await fetchAPI(`/api/citas/dia/${dateStr}`);
    } catch (e) {
      state.selectedDayData = [];
    }
    renderSelectedDayPanel();
  }

  function clearChildren(el){ while(el.firstChild) el.removeChild(el.firstChild); }

  async function fetchTipos(){
    try {
      state.tipos = await fetchAPI('/api/tipos-cita');
      renderTipos();
    } catch (e) {
      console.error(e);
    }
  }

  async function fetchHorario(){
    try{
      state.horario = await fetchAPI('/api/configuracion/horario');
    }catch(e){
      state.horario = {
        semana_inicio: '14:00', semana_fin: '18:00',
        fin_semana_inicio: '09:00', fin_semana_fin: '13:00',
        trabaja_sabado: true, trabaja_domingo: false
      };
    }
  }

  function renderTipos(){
    if(!tipoCitaSelect) return;
    tipoCitaSelect.innerHTML = '<option value="">O elige uno guardado...</option>';
    state.tipos.forEach(t=>{
      const opt = document.createElement('option');
      opt.value = t.nombre;
      opt.textContent = `${t.nombre} (${t.duracion_minutos} min)`;
      tipoCitaSelect.appendChild(opt);
    });
  }

  // Devuelve {id, duracion} si el texto coincide con un tipo guardado, si no devuelve {id: null, duracion: duracionCustom}
  function resolverTipo(){
    const texto = (tipoCitaTexto?.value || '').trim();
    if(!texto) return { id: null, duracion: null, nombre: '' };
    const match = state.tipos.find(t => t.nombre.toLowerCase() === texto.toLowerCase());
    const durEl = document.getElementById('custom-tipo-duracion');
    if(match) return { id: match.id, duracion: match.duracion_minutos, nombre: null };
    return { id: null, duracion: parseInt(durEl?.value||'30',10)||30, nombre: texto };
  }

  // Auto-calcula hora_fin según duración del tipo de cita
  function autoFillHoraFin(force = false){
    if(!hora.value) return;
    if(state.horaFinManual && !force) return;
    const { duracion } = resolverTipo();
    if(!duracion) return; // No autocompletar si aún no hay tipo elegido/escrito
    const [h, m] = hora.value.split(':').map(Number);
    const totalMin = h * 60 + m + duracion;
    horaFin.value = String(Math.floor(totalMin / 60)).padStart(2,'0') + ':' + String(totalMin % 60).padStart(2,'0');
    if(force) state.horaFinManual = false;
  }

  function actualizarSeccionCustom(){
    const sec = document.getElementById('custom-tipo-section');
    if(!sec) return;
    const texto = (tipoCitaTexto?.value || '').trim();
    const esConocido = state.tipos.some(t => t.nombre.toLowerCase() === texto.toLowerCase());
    sec.classList.toggle('hidden', !texto || esConocido);
  }

  // Valida que la cita esté dentro del horario laboral (cliente)
  function validarHorario(fechaStr, horaInicio, horaFinStr){
    const hcfg = state.horario || {
      semana_inicio: '14:00', semana_fin: '18:00',
      fin_semana_inicio: '09:00', fin_semana_fin: '13:00',
      trabaja_sabado: true, trabaja_domingo: false
    };
    const dow = new Date(fechaStr + 'T00:00:00').getDay(); // 0=Dom, 6=Sáb
    const toMin = t => { const [h,m] = t.split(':').map(Number); return h*60+m; };
    const ini = toMin(horaInicio), fin = toMin(horaFinStr);
    if(ini >= fin) return 'La hora de fin debe ser después de la hora de inicio';
    if(dow === 0 && !hcfg.trabaja_domingo) return 'El consultorio no trabaja los domingos';
    if(dow === 6 && !hcfg.trabaja_sabado) return 'El consultorio no trabaja los sábados';

    if(dow === 6 || dow === 0){
      if(ini < toMin(hcfg.fin_semana_inicio) || fin > toMin(hcfg.fin_semana_fin)){
        return `Fin de semana: horario permitido ${hcfg.fin_semana_inicio} a ${hcfg.fin_semana_fin}`;
      }
    } else {
      if(ini < toMin(hcfg.semana_inicio) || fin > toMin(hcfg.semana_fin)){
        return `Entre semana: horario permitido ${hcfg.semana_inicio} a ${hcfg.semana_fin}`;
      }
    }
    return null;
  }

  async function loadMonth(year, month){
    monthLabel.textContent = formatMonthYear(year, month);
    clearChildren(calendarEl);
    const weekdays = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
    weekdays.forEach(d => {
      const w = document.createElement('div');
      w.className = 'weekday-label';
      w.textContent = d;
      calendarEl.appendChild(w);
    });

    const first = new Date(year, month, 1);
    const startDay = (first.getDay() + 6) % 7; // Monday=0
    const daysInMonth = new Date(year, month+1, 0).getDate();

    try {
      state.citasMes = await fetchAPI(`/api/citas/mes/${year}/${month+1}`);
    } catch (e) {
      state.citasMes = {};
    }

    for(let i=0;i<startDay;i++){
      const empty = document.createElement('div');
      calendarEl.appendChild(empty);
    }

    for(let d=1; d<=daysInMonth; d++){
      const cell = document.createElement('div');
      cell.className = 'day-cell touch-target';
      const num = document.createElement('div');
      num.className = 'day-number';
      num.textContent = d;
      cell.appendChild(num);

      if(state.citasMes[d] && state.citasMes[d].length>0){
        cell.classList.add('has-appointment');
        const indicator = document.createElement('div');
        indicator.className = 'indicator';
        cell.appendChild(indicator);
      }

      const isToday = d === state.today.getDate() && month === state.today.getMonth() && year === state.today.getFullYear();
      if(isToday) cell.classList.add('ring-2','ring-primary');

      if(state.selectedDate === `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`){
        cell.classList.add('is-selected');
      }

      // Marcar domingo visualmente
      const dow = new Date(year, month, d).getDay();
      if(dow === 0) cell.classList.add('opacity-40', 'cursor-default');

      cell.addEventListener('click', ()=> openDay(year, month, d));
      calendarEl.appendChild(cell);
    }
  }

  function isCitaVencida(c){
    const hoy = new Date();
    const hoyStr = `${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}-${String(hoy.getDate()).padStart(2,'0')}`;
    if(c.fecha !== hoyStr) return false;
    const [hh, mm] = c.hora_fin.split(':').map(Number);
    const finMin = hh * 60 + mm;
    const nowMin = hoy.getHours() * 60 + hoy.getMinutes();
    return nowMin > finMin;
  }

  async function openDay(year, month, day){
    await loadSelectedDayData(year, month, day);
    await loadMonth(state.year, state.month);

    const clickedDate = new Date(year, month, day);
    modalDate.textContent = clickedDate.toLocaleDateString('es-ES', { weekday:'long', day:'2-digit', month:'long', year:'numeric' });
    modalBody.innerHTML = '<p class="text-gray-400 text-sm">Cargando...</p>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Botón "Agregar cita": solo visible en den días laborales futuros/hoy
    modalAdd.classList.toggle('hidden', (state.isSunday && !(state.horario && state.horario.trabaja_domingo)) || state.isPast);

    if(state.isSunday && !(state.horario && state.horario.trabaja_domingo)){
      modalBody.innerHTML = `
        <div class="flex flex-col items-center gap-2 py-4 text-center">
          <span class="text-3xl">🚫</span>
          <p class="text-sm font-semibold text-gray-600">El consultorio no trabaja los domingos</p>
          <p class="text-xs text-gray-400">Horario: Lun-Vie 14:00-18:00 · Sáb 09:00-13:00</p>
        </div>`;
      return;
    }

    renderDayList();
  }

  function renderDayList(){
    if(!state.selectedDayData || state.selectedDayData.length===0){
      const msg = state.isPast
        ? '<div class="flex flex-col items-center gap-2 py-4 text-center"><span class="text-2xl">📋</span><p class="text-sm text-gray-500">No hubo citas registradas este día</p></div>'
        : '<p class="text-sm text-gray-400">No hay citas para este día.</p>';
      modalBody.innerHTML = msg;
      return;
    }
    modalBody.innerHTML = '';
    state.selectedDayData.forEach(c=>{
      const item = document.createElement('div');
      item.className = 'bg-gray-50 border border-gray-100 rounded-xl p-3 space-y-2';

      if(state.isPast){
        // Vista de día pasado: solo botón reagendar por WhatsApp
        const fechaObj = new Date(c.fecha + 'T00:00:00');
        const fechaFmt = fechaObj.toLocaleDateString('es-ES', { weekday:'long', day:'2-digit', month:'long' });
        const msgWA = encodeURIComponent(
          `Estimado/a ${c.paciente_completo}, le contactamos del Consultorio Dental Castillo.` +
          ` Notamos que tenía una cita el ${fechaFmt} a las ${c.hora_formateada} (${c.tipo}).` +
          ` Nos gustaría ofrecerle la oportunidad de reagendar su cita en el horario que mejor le convenga.` +
          ` Por favor indíquenos su disponibilidad. Quedamos a sus órdenes. 🦷`
        );
        const waLink = `https://wa.me/52${c.telefono}?text=${msgWA}`;
        item.innerHTML = `
          <div class="flex justify-between items-start gap-2">
            <div>
              <div class="font-semibold text-gray-700">${c.paciente_completo}</div>
              <div class="text-xs text-primary/70 font-medium">${c.tipo}</div>
            </div>
            <span class="text-sm font-bold text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">${c.hora_formateada}</span>
          </div>
          <a href="${waLink}" target="_blank"
             class="flex items-center justify-center gap-2 w-full bg-green-500 hover:bg-green-600 text-white text-xs font-medium py-2 px-3 rounded-lg transition">
            <i class="fab fa-whatsapp"></i> Invitar a reagendar
          </a>`;
      } else {
        const vencida = isCitaVencida(c);
        item.innerHTML = `
          <div class="flex justify-between items-start gap-2">
            <div>
              <div class="font-semibold text-gray-800">${c.paciente_completo}</div>
              <div class="text-xs text-primary/70 font-medium">${c.tipo}</div>
            </div>
            <span class="text-sm font-bold text-primary bg-primary/10 px-2 py-1 rounded-lg">${c.hora_formateada}</span>
          </div>
          <div class="flex flex-wrap gap-1.5 text-xs">
            <button data-id="${c.id}" class="btn-accion flex items-center gap-1 bg-primary text-white px-2.5 py-1 rounded-lg" data-action="editar"><i class="fas fa-pen"></i> Editar</button>
            <button data-id="${c.id}" class="btn-accion flex items-center gap-1 bg-green-100 text-green-700 px-2.5 py-1 rounded-lg" data-action="confirmar"><i class="fas fa-check"></i> Confirmar</button>
            <button data-id="${c.id}" class="btn-accion flex items-center gap-1 bg-red-50 text-red-500 px-2.5 py-1 rounded-lg" data-action="cancelar"><i class="fas fa-times"></i> Cancelar</button>
            <button data-id="${c.id}" class="btn-accion flex items-center gap-1 bg-green-500 text-white px-2.5 py-1 rounded-lg" data-action="whatsapp"><i class="fab fa-whatsapp"></i> WhatsApp</button>
            ${vencida ? `<button data-id="${c.id}" class="btn-accion flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-lg" data-action="reagendar"><i class="fas fa-calendar-plus"></i> Reagendar</button>` : ''}
          </div>`;
      }
      modalBody.appendChild(item);
    });

    modalBody.querySelectorAll('.btn-accion').forEach(btn=>{
      btn.addEventListener('click', (e)=>{
        const el = e.target.closest('[data-action]');
        handleAction(el.dataset.action, parseInt(el.dataset.id,10));
      });
    });
  }

  async function handleAction(action, id){
    const cita = state.selectedDayData.find(c=>c.id===id);
    if(!cita) return;
    if(action==='editar'){
      openForm(cita);
    } else if(action==='confirmar'){
      await fetchAPI(`/api/citas/${id}/confirmar`, {method:'POST'});
      showToast('Cita confirmada','success');
      refresh();
    } else if(action==='cancelar'){
      await fetchAPI(`/api/citas/${id}/cancelar`, {method:'POST'});
      showToast('Cita cancelada','warning');
      refresh();
    } else if(action==='whatsapp'){
      try{
        const res = await fetchAPI(`/api/citas/${id}/whatsapp`);
        if(res.whatsapp_link) window.open(res.whatsapp_link, '_blank');
      }catch(e){}
    } else if(action==='reagendar'){
      openForm(cita);
      showToast('Edita fecha/hora y guarda para reagendar','info');
    }
  }

  function openForm(data){
    form.reset();
    state.horaFinManual = false;
    if(tipoCitaSelect) tipoCitaSelect.value = '';
    const secCustom = document.getElementById('custom-tipo-section');
    if(secCustom) secCustom.classList.add('hidden');
    citaId.value = data && data.id ? data.id : '';
    formTitle.textContent = data ? 'Editar cita' : 'Nueva cita';
    deleteBtn.classList.toggle('hidden', !data);

    if(data){
      nombre.value = data.paciente_nombre || data.nombre || '';
      apellidos.value = data.paciente_apellidos || data.apellidos || '';
      telefono.value = data.telefono || '';
      fecha.value = data.fecha;
      hora.value = data.hora_inicio;
      horaFin.value = data.hora_fin || '';
      // Rellenar campo texto con el nombre del tipo
      const tipoMatch = state.tipos.find(t => t.id === (data.tipo_id || data.tipo_cita_id));
      if(tipoCitaTexto) tipoCitaTexto.value = tipoMatch ? tipoMatch.nombre : (data.tipo || '');
      notas.value = data.notas || '';
    } else if(state.selectedDate){
      fecha.value = state.selectedDate;
    }
    formModal.classList.remove('hidden');
    formModal.classList.add('flex');
  }

  function closeFormModal(){ formModal.classList.add('hidden'); formModal.classList.remove('flex'); }
  function closeDayModal(){ modal.classList.add('hidden'); modal.classList.remove('flex'); }

  async function submitForm(e){
    e.preventDefault();
    const errHorario = validarHorario(fecha.value, hora.value, horaFin.value);
    if(errHorario){ showToast(errHorario, 'error'); return; }

    const textoTipo = (tipoCitaTexto?.value || '').trim();
    if(!textoTipo){ showToast('Indica el tipo de cita', 'error'); return; }

    let { id: tipoCitaId, duracion, nombre: nombreNuevo } = resolverTipo();

    // Si es un tipo nuevo (no coincide con ninguno guardado), lo crea
    if(!tipoCitaId){
      try{
        const nuevo = await fetchAPI('/api/tipos-cita', {
          method:'POST',
          body: JSON.stringify({
            nombre: textoTipo,
            duracion_minutos: duracion,
            activo: false
          })
        });
        tipoCitaId = nuevo.id;
        if(window._refreshCalendarTipos) window._refreshCalendarTipos();
      }catch(e){ return; }
    }

    const payload = {
      nombre: nombre.value.trim(),
      apellidos: apellidos.value.trim(),
      telefono: telefono.value.trim(),
      tipo_cita_id: tipoCitaId,
      fecha: fecha.value,
      hora: hora.value,
      hora_fin: horaFin.value,
      notas: notas.value.trim()
    };
    try{
      if(citaId.value){
        await fetchAPI(`/api/citas/${citaId.value}`, {method:'PUT', body: JSON.stringify(payload)});
        showToast('Cita actualizada');
        formModal.classList.add('hidden');
        refresh();
      } else {
        const res = await fetchAPI('/api/citas', {method:'POST', body: JSON.stringify(payload)});
        showToast('Cita creada');
        formModal.classList.add('hidden');
        refresh();
        if(res && res.whatsapp_link) mostrarDialogoWA(res.whatsapp_link, payload.nombre);
      }
    }catch(e){ /* handled by fetchAPI */ }
  }

  function mostrarDialogoWA(waLink, nombrePaciente){
    const dlg = document.createElement('div');
    dlg.className = 'fixed inset-0 flex items-center justify-center z-[60]';
    dlg.innerHTML = `
      <div style="background:rgba(0,0,0,0.45)" class="absolute inset-0"></div>
      <div class="bg-white rounded-2xl shadow-2xl p-5 w-72 space-y-3 relative z-10 mx-4">
        <div class="flex items-center gap-2">
          <i class="fab fa-whatsapp text-2xl text-green-500"></i>
          <p class="font-semibold text-gray-800 text-sm">Notificar a ${nombrePaciente}</p>
        </div>
        <p class="text-xs text-gray-500">¿Desea enviar la confirmación de la cita por WhatsApp al paciente?</p>
        <div class="flex gap-2">
          <button id="wa-dlg-si" class="flex-1 bg-green-500 hover:bg-green-600 text-white rounded-xl py-2 text-sm font-medium transition">Sí, enviar</button>
          <button id="wa-dlg-no" class="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl py-2 text-sm font-medium transition">Ahora no</button>
        </div>
      </div>`;
    document.body.appendChild(dlg);
    document.getElementById('wa-dlg-si').onclick = ()=>{ window.open(waLink,'_blank'); dlg.remove(); };
    document.getElementById('wa-dlg-no').onclick = ()=> dlg.remove();
  }

  async function cancelFromForm(){
    if(!citaId.value) return;
    await fetchAPI(`/api/citas/${citaId.value}/cancelar`, {method:'POST'});
    showToast('Cita cancelada','warning');
    formModal.classList.add('hidden');
    refresh();
  }

  function refresh(){
    loadMonth(state.year, state.month);
    if(state.selectedDate){
      const parts = getSelectedDateParts();
      if(parts){
        loadSelectedDayData(parts.year, parts.month, parts.day);
        if(!modal.classList.contains('hidden')){
          openDay(parts.year, parts.month, parts.day);
        }
      }
    }
    if(typeof loadStats === 'function') loadStats();
  }

  // Event bindings
  prevBtn.addEventListener('click', ()=>{
    state.month--;
    if(state.month<0){ state.month=11; state.year--; }
    loadMonth(state.year, state.month);
  });
  nextBtn.addEventListener('click', ()=>{
    state.month++;
    if(state.month>11){ state.month=0; state.year++; }
    loadMonth(state.year, state.month);
  });
  btnNueva.addEventListener('click', ()=>{ openForm(null); });
  modalAdd.addEventListener('click', ()=>{ openForm(null); });
  closeModal.addEventListener('click', closeDayModal);
  modal.addEventListener('click', (e)=>{ if(e.target===modal) closeDayModal(); });
  closeForm.addEventListener('click', closeFormModal);
  formModal.addEventListener('click', (e)=>{ if(e.target===formModal) closeFormModal(); });
  form.addEventListener('submit', submitForm);
  deleteBtn.addEventListener('click', cancelFromForm);
  hora.addEventListener('change', ()=> autoFillHoraFin(false));
  horaFin.addEventListener('input', ()=>{ state.horaFinManual = true; });
  if(tipoCitaTexto){
    tipoCitaTexto.addEventListener('input', ()=>{ actualizarSeccionCustom(); autoFillHoraFin(true); });
    tipoCitaTexto.addEventListener('change', ()=>{ actualizarSeccionCustom(); autoFillHoraFin(true); });
  }
  if(tipoCitaSelect){
    tipoCitaSelect.addEventListener('change', ()=>{
      if(tipoCitaSelect.value && tipoCitaTexto){
        tipoCitaTexto.value = tipoCitaSelect.value;
      }
      actualizarSeccionCustom();
      autoFillHoraFin(true);
    });
  }
  const customDurEl = document.getElementById('custom-tipo-duracion');
  if(customDurEl) customDurEl.addEventListener('change', ()=> autoFillHoraFin(true));

  // Init
  window._refreshCalendarTipos = fetchTipos;
  window._refreshHorarioConfig = fetchHorario;
  fetchTipos();
  fetchHorario();
  state.selectedDate = `${state.today.getFullYear()}-${String(state.today.getMonth()+1).padStart(2,'0')}-${String(state.today.getDate()).padStart(2,'0')}`;
  loadMonth(state.year, state.month);
  loadSelectedDayData(state.today.getFullYear(), state.today.getMonth(), state.today.getDate());
})();
