(function () {
  "use strict";

  const root = document.getElementById("monthly-app");
  if (!root) return;

  const urls = {
    data: root.dataset.dataUrl,
    create: root.dataset.createUrl,
    import: root.dataset.importUrl,
    sections: root.dataset.sectionsUrl,
    period: root.dataset.periodUrl,
    preferences: root.dataset.preferencesUrl,
    activities: root.dataset.activitiesUrl
  };
  const isAdmin = root.dataset.userRole === "admin";
  const userId = root.dataset.userId;
  const ownerFilter = document.getElementById("owner-filter");
  const ownerTarget = document.getElementById("activity-owner");
  const unitInput = document.getElementById("activity-unit");
  const typeInput = document.getElementById("activity-type");
  const form = document.getElementById("activity-form");
  const message = document.getElementById("monthly-message");
  const monthInput = document.getElementById("report-month");
  const report = document.getElementById("monthly-report");
  const sectionFields = [...document.querySelectorAll(".report-ongoing, .report-issues")];
  const sessionFields = [document.getElementById("sessions-field"), document.getElementById("participants-field")];
  const educationDetails = document.getElementById("education-details");
  const logoInputs = [
    ["left_logo", document.getElementById("left-logo-file")],
    ["right_logo", document.getElementById("right-logo-file")]
  ];
  const state = { owners: [], activities: [], sections: [], periods: [], preferences: [], types: {}, statuses: [] };
  let editingId = null;
  let editingClientId = null;
  let settingsTimer = null;
  let selectedOwner = root.dataset.selectedOwner || "";

  function showMessage(text, kind) {
    message.textContent = text;
    message.className = "alert alert-" + (kind || "info");
    message.classList.remove("d-none");
  }

  async function request(url, method, payload) {
    const options = { method: method || "GET", headers: {} };
    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "İstek tamamlanamadı.");
    return result;
  }

  function selectedOwnerId() {
    return isAdmin ? selectedOwner : userId;
  }

  function targetOwnerId() {
    return isAdmin ? ownerTarget.value : userId;
  }

  function currentPeriod() {
    return monthInput.value;
  }

  function ownerFor(id) {
    return state.owners.find(owner => String(owner.id) === String(id));
  }

  function periodFor(ownerId, month) {
    return state.periods.find(period =>
      String(period.owner_id) === String(ownerId) && period.month === month
    );
  }

  function isLocked(ownerId, month) {
    const period = periodFor(ownerId, month);
    return Boolean(period && period.approved_at);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function updateActivityTypes() {
    const unit = unitInput.value;
    typeInput.replaceChildren();
    (state.types[unit] || []).forEach(type => {
      const option = document.createElement("option");
      option.value = type;
      option.textContent = type;
      typeInput.append(option);
    });
    const isEducation = unit === "Eğitim";
    sessionFields.forEach(field => field.classList.toggle("d-none", !isEducation));
    educationDetails.classList.toggle("d-none", !isEducation);
  }

  function reportRowsFor(ownerId) {
    return state.activities.filter(activity =>
      String(activity.owner_id) === String(ownerId) &&
      activity.activity_date.slice(0, 7) === currentPeriod()
    );
  }

  function sectionFor(ownerId, unit) {
    return state.sections.find(section =>
      String(section.owner_id) === String(ownerId) &&
      section.month === currentPeriod() &&
      section.unit === unit
    ) || {
      ongoing: unit === "Bilgi Sistemleri"
        ? "Rutin olarak personelin arıza ve yardım talepleri karşılanmaktadır."
        : unit === "Eğitim"
          ? "Okul ve Afet Farkındalık Eğitimleri talep edilen ve planlanan şekilde devam etmektedir."
          : "",
      issues: ""
    };
  }

  function preferenceFor(ownerId) {
    return state.preferences.find(preference =>
      String(preference.owner_id) === String(ownerId)
    ) || { left_logo: "", right_logo: "" };
  }

  function loadReportSettings() {
    const ownerId = selectedOwnerId();
    const canEdit = Boolean(ownerId);
    const locked = canEdit && isLocked(ownerId, currentPeriod());
    sectionFields.forEach(field => {
      const section = canEdit ? sectionFor(ownerId, field.dataset.unit) : { ongoing: "", issues: "" };
      field.value = field.classList.contains("report-ongoing") ? section.ongoing : section.issues;
      field.disabled = !canEdit || locked;
    });
    logoInputs.forEach(([, input]) => { input.disabled = !canEdit; });
    renderReport();
    updateApprovalUI();
  }

  function activityTable(rows) {
    if (!rows.length) return "<p><i>Bu dönem için kayıt bulunamadı.</i></p>";
    if (rows[0].unit === "Eğitim") {
      const groups = new Map();
      rows.forEach(row => {
        if (!groups.has(row.activity_type)) {
          groups.set(row.activity_type, { sessions: 0, participants: 0, dates: [], details: [] });
        }
        const group = groups.get(row.activity_type);
        group.sessions += row.sessions || 0;
        group.participants += row.participants || 0;
        group.dates.push(row.activity_date);
        const detail = [row.institution, row.participant_group ? "(" + row.participant_group + ")" : "", row.description]
          .filter(Boolean).join(" ");
        if (detail && !group.details.includes(detail)) group.details.push(detail);
      });
      let totalSessions = 0;
      let totalParticipants = 0;
      const body = [...groups.entries()].map(([name, group], index) => {
        group.dates.sort();
        totalSessions += group.sessions;
        totalParticipants += group.participants;
        const range = group.dates[0] === group.dates[group.dates.length - 1]
          ? formatDate(group.dates[0])
          : formatDate(group.dates[0]) + " – " + formatDate(group.dates[group.dates.length - 1]);
        return "<tr><td>" + (index + 1) + "</td><td>" + escapeHtml(name) +
          "</td><td>Ay içerisinde yapılan eğitim sayısı: " + group.sessions +
          (group.details.length ? "<br>" + group.details.map(escapeHtml).join("; ") : "") +
          "</td><td>" + range + "</td><td>" + group.participants + " kişi</td></tr>";
      }).join("");
      return "<table><thead><tr><th>No</th><th>Faaliyet / İşlem</th><th>Açıklama</th><th>Tarih</th><th>Katılımcı</th></tr></thead><tbody>" +
        body + "<tr><td colspan='3'></td><td><b>TOPLAM</b></td><td><b>" + totalParticipants +
        " kişi (" + totalSessions + " eğitim)</b></td></tr></tbody></table>";
    }
    const sorted = rows.slice().sort((a, b) => a.activity_date.localeCompare(b.activity_date));
    return "<table><thead><tr><th>No</th><th>Faaliyet / İşlem</th><th>Açıklama</th><th>Tarih</th><th>Sonuç / Durum</th></tr></thead><tbody>" +
      sorted.map((row, index) => "<tr><td>" + (index + 1) + "</td><td>" +
        escapeHtml(row.activity_type) + "</td><td>" +
        escapeHtml([row.institution, row.participant_group, row.description].filter(Boolean).join(" – ")) +
        "</td><td>" + formatDate(row.activity_date) + "</td><td>" + escapeHtml(row.status) + "</td></tr>"
      ).join("") + "</tbody></table>";
  }

  function formatDate(isoDate) {
    const parts = isoDate.split("-");
    return parts.length === 3 ? parts[2] + "." + parts[1] + "." + parts[0] : isoDate;
  }

  function reportBlock(owner, unit) {
    const rows = reportRowsFor(owner.id).filter(row => row.unit === unit);
    const section = sectionFor(owner.id, unit);
    const period = periodFor(owner.id, currentPeriod());
    const preferences = preferenceFor(owner.id);
    const monthName = new Intl.DateTimeFormat("tr-TR", { month: "long", year: "numeric" })
      .format(new Date(currentPeriod() + "-01T12:00:00")).toLocaleUpperCase("tr-TR");
    const leftLogo = preferences.left_logo
      ? "<img class='monthly-logo' src='" + escapeHtml(preferences.left_logo) + "' alt='Sol logo'>"
      : "<div class='monthly-logo-placeholder'>Sol logo</div>";
    const rightLogo = preferences.right_logo
      ? "<img class='monthly-logo' src='" + escapeHtml(preferences.right_logo) + "' alt='Sağ logo'>"
      : "<div class='monthly-logo-placeholder'>Sağ logo</div>";
    return "<article class='monthly-report-page'>" +
      "<div class='monthly-report-heading'>" + leftLogo +
      "<h3>AYLIK FAALİYET RAPORU</h3>" + rightLogo + "</div>" +
      "<p><b>Rapor Dönemi:</b> " + escapeHtml(monthName) +
      "<br><b>Hazırlayan Birim:</b> " + escapeHtml(owner.department || "Şube") +
      " <b>(" + escapeHtml(unit) + ")</b><br><b>Şube Müdürü:</b> " +
      escapeHtml(owner.full_name) + "<br><b>Rapor Tarihi:</b> " +
      escapeHtml(new Date().toLocaleDateString("tr-TR")) + "</p>" +
      "<h4>1. Genel Bilgiler</h4><p>Şube Müdürlüğünün görev alanına ilişkin çalışmalar bu rapor döneminde planlanan takvim doğrultusunda yürütülmüştür.</p>" +
      "<h4>2. Ay İçerisinde Yapılan Çalışmalar</h4>" + activityTable(rows) +
      "<h4>3. Devam Eden Çalışmalar</h4><p>" +
      (escapeHtml(section.ongoing).replace(/\n/g, "<br>") || "-") +
      "</p><h4>4. Sorunlar ve Çözüm Önerileri</h4><p>" +
      (escapeHtml(section.issues).replace(/\n/g, "<br>") || "Bu dönemde bildirilen sorun bulunmamaktadır.") +
      "</p><h4>5. Ay Sonu Genel Değerlendirme</h4>" +
      "<p>Bu rapor döneminde şube müdürlüğü tarafından yürütülen çalışmalar genel olarak başarıyla tamamlanmış olup, devam eden projelerin sonraki ayda sonuçlandırılması planlanmaktadır.</p>" +
      "<div class='monthly-sign'><b>Şube Müdürü</b><br>" + escapeHtml(owner.full_name) +
      "<br>İmza" + (period && period.approved_at ? "<br><small>Ay sonu onayı: " + escapeHtml(period.approved_at) + "</small>" : "") +
      "</div><div class='monthly-footer'><b>Sivas İl Afet ve Acil Durum Müdürlüğü</b><br>" +
      "Eğriköprü Mah. Erhan Üstündağ Cad. No:1 58050 Merkez / Sivas</div></article>";
  }

  function renderReport() {
    if (!currentPeriod()) {
      report.replaceChildren();
      return;
    }
    const owners = selectedOwnerId()
      ? state.owners.filter(owner => String(owner.id) === String(selectedOwnerId()))
      : state.owners;
    const html = owners.flatMap(owner =>
      Object.keys(state.types).map(unit => reportBlock(owner, unit))
    ).join("");
    report.innerHTML = html || "<p class='text-secondary'>Rapor oluşturmak için önce bir şube müdürü ekleyin.</p>";
  }

  function updateApprovalUI() {
    const ownerId = selectedOwnerId();
    const period = ownerId && periodFor(ownerId, currentPeriod());
    const approved = Boolean(period && period.approved_at);
    const button = document.getElementById("toggle-approval");
    button.disabled = !ownerId;
    button.textContent = approved ? "Kilidi aç" : "Ayı onayla ve kilitle";
    document.getElementById("approval-status").textContent = !ownerId
      ? "Onay ve düzenleme için belirli bir şube müdürü seçin."
      : approved
        ? "Bu ay " + period.approved_at + " tarihinde onaylandı. Kayıt ve rapor metinleri kilitlendi."
        : "Ay henüz onaylanmadı.";
    const activityMonth = document.getElementById("activity-date").value.slice(0, 7);
    const activityLocked = Boolean(targetOwnerId() && isLocked(targetOwnerId(), activityMonth));
    form.querySelectorAll("input, select, textarea, button").forEach(element => {
      if (element.id !== "activity-cancel") element.disabled = activityLocked;
    });
    document.getElementById("activity-cancel").disabled = false;
    sectionFields.forEach(field => { field.disabled = !ownerId || approved; });
    logoInputs.forEach(([, input]) => { input.disabled = !ownerId || approved; });
  }

  function renderActivities() {
    const body = document.getElementById("activity-list");
    body.replaceChildren();
    const rows = state.activities.slice().sort((a, b) =>
      b.activity_date.localeCompare(a.activity_date) || b.id - a.id
    );
    document.getElementById("activity-count").textContent = rows.length + " kayıt";
    rows.forEach(activity => {
      const row = document.createElement("tr");
      const values = [
        formatDate(activity.activity_date),
        (activity.department || "") + " — " + (activity.owner_name || ""),
        activity.unit,
        activity.activity_type,
        [activity.institution, activity.participant_group, activity.description].filter(Boolean).join(" – "),
        activity.status,
        activity.unit === "Eğitim" ? activity.sessions + " / " + activity.participants : ""
      ];
      values.forEach(value => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      const actions = document.createElement("td");
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "btn btn-sm btn-outline-primary me-1";
      edit.textContent = "Düzenle";
      edit.dataset.action = "edit";
      edit.dataset.id = activity.id;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-sm btn-outline-danger";
      remove.textContent = "Sil";
      remove.dataset.action = "delete";
      remove.dataset.id = activity.id;
      const locked = isLocked(activity.owner_id, activity.activity_date.slice(0, 7));
      edit.disabled = locked;
      remove.disabled = locked;
      actions.append(edit, remove);
      row.append(actions);
      body.append(row);
    });
    updateApprovalUI();
  }

  function resetForm() {
    editingId = null;
    editingClientId = null;
    form.reset();
    document.getElementById("activity-date").value = new Date().toISOString().slice(0, 10);
    document.getElementById("activity-form-title").textContent = "Yeni faaliyet kaydı";
    document.getElementById("activity-submit").textContent = "Kaydı ekle";
    document.getElementById("activity-cancel").classList.add("d-none");
    if (isAdmin) ownerTarget.value = selectedOwner;
    updateActivityTypes();
    updateApprovalUI();
  }

  function editActivity(activity) {
    editingId = activity.id;
    editingClientId = activity.client_id;
    if (isAdmin) ownerTarget.value = activity.owner_id;
    unitInput.value = activity.unit;
    updateActivityTypes();
    typeInput.value = activity.activity_type;
    document.getElementById("activity-date").value = activity.activity_date;
    document.getElementById("activity-status").value = activity.status;
    document.getElementById("activity-sessions").value = activity.sessions;
    document.getElementById("activity-participants").value = activity.participants;
    document.getElementById("activity-institution").value = activity.institution;
    document.getElementById("activity-group").value = activity.participant_group;
    document.getElementById("activity-description").value = activity.description;
    document.getElementById("activity-form-title").textContent = "Faaliyet kaydını düzenle";
    document.getElementById("activity-submit").textContent = "Değişikliği kaydet";
    document.getElementById("activity-cancel").classList.remove("d-none");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function refresh() {
    const query = selectedOwner ? "?owner_id=" + encodeURIComponent(selectedOwner) : "";
    const data = await request(urls.data + query);
    state.owners = data.owners;
    state.activities = data.activities;
    state.sections = data.sections;
    state.periods = data.periods;
    state.preferences = data.preferences;
    state.types = data.activity_types;
    state.statuses = data.statuses;
    updateActivityTypes();
    renderActivities();
    loadReportSettings();
  }

  async function saveSections() {
    const ownerId = selectedOwnerId();
    if (!ownerId || isLocked(ownerId, currentPeriod())) return;
    const sections = {};
    Object.keys(state.types).forEach(unit => {
      const ongoingField = [...document.querySelectorAll(".report-ongoing")]
        .find(field => field.dataset.unit === unit);
      const issuesField = [...document.querySelectorAll(".report-issues")]
        .find(field => field.dataset.unit === unit);
      sections[unit] = {
        ongoing: ongoingField.value,
        issues: issuesField.value
      };
    });
    try {
      await request(urls.sections, "PUT", { owner_id: ownerId, month: currentPeriod(), sections });
      await refresh();
      showMessage("Rapor metinleri kaydedildi.", "success");
    } catch (error) {
      showMessage(error.message, "danger");
    }
  }

  async function importLegacyData(backup) {
    let records = [];
    let locks = {};
    let logos = {};
    if (backup) {
      if (typeof backup !== "object" || Array.isArray(backup)) {
        showMessage("Yedek dosyasının biçimi geçersiz.", "danger");
        return;
      }
      records = backup.records || backup.recs || [];
      locks = backup.locks || {};
      logos = backup.logos || {};
    } else {
      try {
        const rawRecords = localStorage.getItem("recs");
        records = rawRecords ? JSON.parse(rawRecords) : [];
        locks = JSON.parse(localStorage.getItem("locks") || "{}");
        logos = JSON.parse(localStorage.getItem("logos") || "{}");
      } catch (error) {
        showMessage("Bu tarayıcıdaki eski kayıtları okuyamadım. localStorage verisi geçersiz.", "danger");
        return;
      }
    }
    if (!Array.isArray(records) || !locks || typeof locks !== "object" || !logos || typeof logos !== "object") {
      showMessage("Eski prototip verilerinin biçimi geçersiz.", "danger");
      return;
    }
    const ownerId = targetOwnerId();
    if (!ownerId) {
      showMessage("Eski kayıtların hangi şubeye ait olduğunu seçin.", "warning");
      return;
    }
    const normalized = records.map(record => {
      if (!record || typeof record !== "object" || Array.isArray(record)) return {};
      return {
        ...record,
        client_id: String(record.client_id || record.id || ""),
        unit: record.unit === "Eğitim Şube" ? "Eğitim" : record.unit,
        type: record.type || record.activity_type,
        date: record.date || record.activity_date,
        description: record.desc || record.description || "",
        sessions: record.sess == null ? record.sessions : record.sess,
        participants: record.ppl == null ? record.participants : record.ppl,
        institution: record.kur || record.institution || "",
        participant_group: record.grp || record.participant_group || ""
      };
    });
    try {
      const result = await request(urls.import, "POST", { owner_id: ownerId, records: normalized, locks, logos });
      await refresh();
      showMessage(
        result.imported + " eski kayıt içe aktarıldı; " + result.duplicates +
        " kayıt zaten vardı; " + result.skipped + " geçersiz/kilitli kayıt atlandı. Eski tarayıcı verisi silinmedi.",
        "success"
      );
    } catch (error) {
      showMessage(error.message, "danger");
    }
  }

  function imageAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Logo dosyası okunamadı."));
      reader.onload = () => {
        const image = new Image();
        image.onerror = () => reject(new Error("Seçilen dosya bir görüntü değil."));
        image.onload = () => {
          const scale = Math.min(1, 240 / Math.max(image.width, image.height));
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(image.width * scale));
          canvas.height = Math.max(1, Math.round(image.height * scale));
          canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/png"));
        };
        image.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function saveLogo(key, input) {
    if (!input.files.length) return;
    const ownerId = selectedOwnerId();
    if (!ownerId) {
      showMessage("Logo kaydetmek için bir şube müdürü seçin.", "warning");
      input.value = "";
      return;
    }
    try {
      const image = await imageAsDataUrl(input.files[0]);
      const preferences = preferenceFor(ownerId);
      preferences[key] = image;
      await request(urls.preferences, "PUT", {
        owner_id: ownerId,
        left_logo: preferences.left_logo || "",
        right_logo: preferences.right_logo || ""
      });
      await refresh();
      showMessage("Logo kaydedildi.", "success");
    } catch (error) {
      showMessage(error.message, "danger");
    } finally {
      input.value = "";
    }
  }

  ownerFilter?.addEventListener("change", () => {
    const url = new URL(window.location.href);
    if (ownerFilter.value) url.searchParams.set("owner_id", ownerFilter.value);
    else url.searchParams.delete("owner_id");
    window.location.assign(url);
  });

  unitInput.addEventListener("change", updateActivityTypes);
  document.getElementById("activity-date").addEventListener("change", updateApprovalUI);
  ownerTarget.addEventListener("change", updateApprovalUI);
  monthInput.value = new Date().toISOString().slice(0, 7);
  monthInput.addEventListener("change", loadReportSettings);
  document.getElementById("activity-cancel").addEventListener("click", resetForm);
  document.getElementById("import-legacy")?.addEventListener("click", () => importLegacyData());
  document.getElementById("legacy-file")?.addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const backup = JSON.parse(await file.text());
      await importLegacyData(backup);
    } catch (error) {
      showMessage("Yedek dosyası okunamadı veya JSON biçimi geçersiz.", "danger");
    } finally {
      event.target.value = "";
    }
  });
  document.getElementById("print-report").addEventListener("click", () => window.print());
  document.getElementById("copy-report").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(report.innerText);
      document.getElementById("copy-message").textContent = "Rapor panoya kopyalandı.";
    } catch (error) {
      document.getElementById("copy-message").textContent = "Kopyalama başarısız. Yazdır / PDF seçeneğini kullanın.";
    }
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const ownerId = targetOwnerId();
    if (!ownerId) {
      showMessage("Kayıt eklemek için şube müdürü seçin.", "warning");
      return;
    }
    const payload = {
      owner_id: ownerId,
      client_id: editingClientId || (window.crypto && crypto.randomUUID
        ? crypto.randomUUID()
        : Date.now() + "-" + Math.random().toString(16).slice(2)),
      unit: unitInput.value,
      type: typeInput.value,
      date: document.getElementById("activity-date").value,
      status: document.getElementById("activity-status").value,
      sessions: document.getElementById("activity-sessions").value,
      participants: document.getElementById("activity-participants").value,
      institution: document.getElementById("activity-institution").value,
      participant_group: document.getElementById("activity-group").value,
      description: document.getElementById("activity-description").value
    };
    try {
      const editUrl = urls.activities + "/" + editingId;
      const wasEditing = Boolean(editingId);
      await request(editingId ? editUrl : urls.create, editingId ? "PUT" : "POST", payload);
      resetForm();
      await refresh();
      showMessage(wasEditing ? "Faaliyet güncellendi." : "Faaliyet eklendi.", "success");
    } catch (error) {
      showMessage(error.message, "danger");
    }
  });

  document.getElementById("activity-list").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const activity = state.activities.find(item => String(item.id) === button.dataset.id);
    if (!activity) return;
    if (button.dataset.action === "edit") {
      editActivity(activity);
      return;
    }
    if (!window.confirm("Bu faaliyet kaydını silmek istiyor musunuz?")) return;
    try {
      await request(urls.activities + "/" + activity.id, "DELETE");
      await refresh();
      showMessage("Faaliyet silindi.", "success");
    } catch (error) {
      showMessage(error.message, "danger");
    }
  });

  sectionFields.forEach(field => field.addEventListener("input", () => {
    window.clearTimeout(settingsTimer);
    settingsTimer = window.setTimeout(saveSections, 600);
  }));

  document.getElementById("toggle-approval").addEventListener("click", async () => {
    const ownerId = selectedOwnerId();
    if (!ownerId) return;
    try {
      const result = await request(urls.period, "POST", { owner_id: ownerId, month: currentPeriod() });
      await refresh();
      showMessage(result.approved ? "Ay onaylandı ve kilitlendi." : "Ayın kilidi açıldı.", "success");
    } catch (error) {
      showMessage(error.message, "danger");
    }
  });

  logoInputs.forEach(([key, input]) => input.addEventListener("change", () => saveLogo(key, input)));

  updateActivityTypes();
  document.getElementById("activity-date").value = new Date().toISOString().slice(0, 10);
  refresh().catch(error => showMessage(error.message, "danger"));
})();
