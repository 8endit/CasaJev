let manageData = null;
let manageTab = '';

function notice(text) {
  $('manageNotice').textContent = text;
}

function button(text, fn, cls = '') {
  const b = node('button', text, cls);
  b.type = 'button';
  b.onclick = async () => {
    b.disabled = true;
    try {
      await fn();
    } catch (error) {
      notice(error.message);
    } finally {
      b.disabled = false;
    }
  };
  return b;
}

function row(title, subtitle, buttons = []) {
  const element = node('div', undefined, 'row');
  const main = node('div', undefined, 'row-main');
  main.append(node('strong', title), node('small', subtitle));
  const actions = node('div', undefined, 'actions');
  actions.append(...buttons);
  element.append(main, actions);
  return { element, main };
}

function field(form, title, value = '', type = 'text', help = '') {
  const label = node('label');
  label.append(node('span', title));
  const input = node(type === 'textarea' ? 'textarea' : 'input');
  if (type !== 'textarea') input.type = type;
  input.value = value;
  label.append(input);
  if (help) label.append(node('span', help, 'field-help'));
  form.append(label);
  return input;
}

function selectField(form, title, value, choices, help = '') {
  const block = node('div', undefined, 'field-block');
  const label = node('label', title);
  const select = node('select');
  for (const [id, text] of choices) {
    const option = node('option', text);
    option.value = id;
    option.selected = id === value;
    select.append(option);
  }
  label.append(select);
  block.append(label);
  if (help) block.append(node('span', help, 'field-help'));
  form.append(block);
  return select;
}

function check(form, title, value = false) {
  const label = node('label', undefined, 'check');
  const input = node('input');
  input.type = 'checkbox';
  input.checked = value;
  label.append(input, node('span', title));
  form.append(label);
  return input;
}

function submit(form, text, fn) {
  const b = node('button', text, 'primary');
  b.type = 'submit';
  b.setAttribute('aria-label', text);
  form.append(b);
  form.onsubmit = async event => {
    event.preventDefault();
    notice('');
    b.disabled = true;
    try {
      await fn();
    } catch (error) {
      notice(error.message);
    } finally {
      b.disabled = false;
    }
  };
}

function details(parent, title, value) {
  const detail = node('details');
  detail.append(
    node('summary', title),
    node('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2)),
  );
  parent.append(detail);
}

function sectionHeading(title, subtitle = '') {
  const heading = node('div', undefined, 'section-heading');
  heading.append(node('h3', title));
  if (subtitle) heading.append(node('p', subtitle));
  return heading;
}

function modal(title, { navigation = false, onboarding = false } = {}) {
  $('manageTitle').textContent = title;
  $('manageContent').replaceChildren();
  notice('');
  $('manageNav').classList.toggle('hidden', !navigation);
  $('manageDialog').classList.toggle('onboarding-dialog', onboarding);
  if (!$('manageDialog').open) $('manageDialog').showModal();
  return $('manageContent');
}

$('closeManage').onclick = () => $('manageDialog').close();
$('settingsToggle').onclick = () => manage('settings');
document.querySelectorAll('[data-manage]').forEach(item => {
  item.onclick = () => manage(item.dataset.manage);
});

function setActiveManageTab(tab) {
  document.querySelectorAll('[data-manage]').forEach(item => {
    item.setAttribute('aria-current', item.dataset.manage === tab ? 'page' : 'false');
  });
}

async function chatMenu(chat) {
  $('historyDialog').close();
  const box = modal('Chat verwalten');
  const form = node('form');
  const title = field(form, 'Titel', chat.title);
  title.maxLength = 120;
  submit(form, 'Titel speichern', async () => {
    await api('/api/chats/meta', { id: chat.id, changes: { title: title.value } });
    $('manageDialog').close();
    showHistory();
  });
  box.append(form);
  const actions = node('div', undefined, 'actions');
  actions.style.marginTop = '20px';
  actions.append(
    button(chat.pinned ? 'Nicht mehr anheften' : 'Chat anheften', async () => {
      await api('/api/chats/meta', { id: chat.id, changes: { pinned: !chat.pinned } });
      $('manageDialog').close();
      showHistory();
    }),
    button(chat.archived ? 'Wiederherstellen' : 'Archivieren', async () => {
      await api('/api/chats/meta', { id: chat.id, changes: { archived: !chat.archived } });
      $('manageDialog').close();
      showHistory();
    }),
    button('Als Datei speichern', async () => {
      download('CasaJev-Chat.json', await api('/api/chat/' + chat.id));
    }),
  );
  box.append(actions);
}

function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const anchor = node('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const RESULT_LABELS = {
  arguments_included: 'Argumente enthalten',
  cpu_percent: 'CPU',
  elapsed: 'Laufzeit',
  extra_duplicates: 'Zusätzliche Dubletten',
  groups: 'Gruppen',
  matches: 'Treffer',
  memory_percent: 'RAM',
  name: 'Name',
  pid: 'PID',
  processes: 'Prozesse',
  records: 'Datensätze',
  truncated: 'Gekürzt',
};

function resultLabel(key) {
  return RESULT_LABELS[key] || key.replaceAll('_', ' ').replace(/^./, character => character.toUpperCase());
}

function resultValue(value, key = '') {
  if (value === null || value === undefined) return '–';
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nein';
  if (typeof value === 'number') {
    const formatted = value.toLocaleString('de-DE', { maximumFractionDigits: 2 });
    return key.endsWith('_percent') ? formatted + ' %' : formatted;
  }
  return String(value);
}

function resultTable(rows, title = '') {
  const box = node('div', undefined, 'result-view');
  if (title) box.append(node('div', title, 'result-title'));
  const columns = [...new Set(rows.slice(0, 50).flatMap(item => Object.keys(item)))].slice(0, 8);
  const wrapper = node('div', undefined, 'result-table-wrap');
  const table = node('table', undefined, 'result-table');
  const header = node('tr');
  for (const column of columns) header.append(node('th', resultLabel(column)));
  const head = node('thead');
  head.append(header);
  table.append(head);
  const body = node('tbody');
  for (const item of rows.slice(0, 25)) {
    const tr = node('tr');
    for (const column of columns) {
      const value = item[column];
      tr.append(node('td', value !== null && typeof value === 'object' ? JSON.stringify(value) : resultValue(value, column)));
    }
    body.append(tr);
  }
  table.append(body);
  wrapper.append(table);
  box.append(wrapper);
  if (rows.length > 25) box.append(node('div', '25 von ' + rows.length + ' Einträgen angezeigt', 'result-note'));
  return box;
}

function resultCards(value) {
  const box = node('dl', undefined, 'result-cards');
  for (const [key, item] of Object.entries(value)) {
    box.append(node('dt', resultLabel(key)), node('dd', resultValue(item, key)));
  }
  return box;
}

function rawResult(value) {
  const detail = node('details', undefined, 'result-raw');
  detail.append(node('summary', 'Technische Daten anzeigen'), node('pre', JSON.stringify(value, null, 2), 'result'));
  return detail;
}

function renderResult(value) {
  if (Array.isArray(value)) {
    if (value.length && value.every(item => item && typeof item === 'object' && !Array.isArray(item))) {
      return resultTable(value);
    }
    const list = node('ul', undefined, 'result-list');
    for (const item of value.slice(0, 50)) list.append(node('li', resultValue(item)));
    return list;
  }
  if (value && typeof value === 'object') {
    if (Array.isArray(value.processes) && value.processes.every(item => item && typeof item === 'object')) {
      return resultTable(value.processes, 'Laufende Prozesse');
    }
    const entries = Object.entries(value);
    if (entries.every(([, item]) => item === null || ['string', 'number', 'boolean'].includes(typeof item))) {
      return resultCards(value);
    }
    const tabular = entries.find(([, item]) => Array.isArray(item) && item.length &&
      item.every(row => row && typeof row === 'object' && !Array.isArray(row)));
    if (tabular) return resultTable(tabular[1], resultLabel(tabular[0]));
    return rawResult(value);
  }
  return node('div', resultValue(value), 'result-value');
}

function messageActions(message, conversation) {
  const box = node('div', undefined, 'message-actions');
  if (message.execution) {
    const parts = [];
    if (Number.isFinite(message.execution.jev_calls)) {
      parts.push(message.execution.jev_calls + ' Jev-' + (message.execution.jev_calls === 1 ? 'Entscheidung' : 'Entscheidungen'));
    }
    if (Number.isFinite(message.execution.gpt_calls)) {
      parts.push(message.execution.gpt_calls + ' GPT-' + (message.execution.gpt_calls === 1 ? 'Aufruf' : 'Aufrufe'));
    }
    if (parts.length) {
      const info = node('span', parts.join(' · '), 'timing');
      info.title = message.execution.verification || 'Technische Ausführungsdaten';
      box.append(info);
    }
  }
  if (message === conversation.messages.at(-1) && ['paused', 'error'].includes(message.status)) {
    box.append(button('Fortsetzen', async () => {
      try {
        await api('/api/chat/resume', { id: cid });
        signature = '';
        refresh();
      } catch (error) {
        $('error').textContent = error.message;
      }
    }, 'small-action'));
  }
  return box;
}

$('stop').onclick = async () => {
  try {
    await api('/api/chat/stop', { id: cid });
    $('stop').textContent = 'Wird angehalten …';
  } catch (error) {
    $('error').textContent = error.message;
  } finally {
    setTimeout(() => { $('stop').textContent = '■ Anhalten'; }, 1500);
  }
};

async function manage(tab) {
  manageTab = tab;
  const isOnboarding = tab === 'onboarding';
  const title = isOnboarding ? 'CasaJev ist bereit' : 'Einstellungen';
  const box = modal(title, { navigation: !isOnboarding, onboarding: isOnboarding });
  if (!isOnboarding) setActiveManageTab(tab);
  box.append(node('p', 'Einen Moment …', 'intro'));
  try {
    manageData = await api('/api/manage');
    box.replaceChildren();
    const renderers = {
      settings: renderSettings,
      accounts: renderAccounts,
      extensions: renderExtensions,
      onboarding: renderOnboarding,
    };
    renderers[tab](box);
    if (manageData.busy) notice('Gerade läuft ein Auftrag. Änderungen gelten, sobald er beendet oder angehalten wurde.');
  } catch (error) {
    notice(error.message);
  }
}

function humanToolName(name) {
  return {
    csv_exact_duplicate_groups: 'Doppelte CSV-Zeilen finden',
    sum_cents_by_category: 'Beträge nach Kategorie summieren',
    sort_numbers: 'Zahlen sortieren',
    sum_numbers: 'Zahlen addieren',
    positive_numbers: 'Positive Zahlen filtern',
    calculate_percentage_of_base: 'Prozentwert berechnen',
  }[name] || name.replaceAll('_', ' ');
}

function renderExtensions(box) {
  box.append(node('p', 'Diese Bereiche brauchst du nur, wenn du CasaJev gezielt erweitern möchtest.', 'intro'));
  box.append(sectionHeading('Eigene Anleitungen', manageData.skills.length + ' vorhanden'));
  box.append(button('Neue Anleitung', () => skillEditor()));
  for (const skill of manageData.skills) {
    box.append(row(
      skill.name,
      (skill.enabled ? 'Aktiv · ' : 'Inaktiv · ') + skill.description,
      [
        button('Bearbeiten', () => skillEditor(skill)),
        button(skill.enabled ? 'Deaktivieren' : 'Aktivieren', async () => {
          await api('/api/skills/save', { ...skill, enabled: !skill.enabled });
          await manage('extensions');
        }),
      ],
    ).element);
  }
  if (!manageData.skills.length) box.append(node('div', 'Noch keine eigenen Anleitungen.', 'empty-note'));

  box.append(sectionHeading('Werkzeuge', manageData.tools.length + ' verfügbar'));
  for (const tool of manageData.tools) {
    const item = row(
      humanToolName(tool.spec.name),
      tool.spec.description,
      [
        button('Prüfen', async () => {
          await api('/api/tools/verify', { id: tool.id });
          notice(humanToolName(tool.spec.name) + ' wurde erfolgreich geprüft.');
        }),
        button(tool.active ? 'Deaktivieren' : 'Aktivieren', async () => {
          await api('/api/tools/toggle', { id: tool.id, active: !tool.active });
          await manage('extensions');
        }),
      ],
    );
    item.main.append(node('span', tool.active ? 'Aktiv' : 'Inaktiv', 'badge'));
    details(item.main, 'Technische Details', {
      input: tool.spec.input_schema,
      output: tool.spec.output_schema,
      evidence: tool.evidence,
    });
    box.append(item.element);
  }
}

function skillEditor(skill = {}) {
  const box = modal(skill.id ? 'Anleitung bearbeiten' : 'Neue Anleitung');
  const form = node('form');
  const name = field(form, 'Name', skill.name || '');
  name.maxLength = 80;
  name.required = true;
  const description = field(form, 'Kurzbeschreibung', skill.description || '');
  description.required = true;
  description.maxLength = 300;
  const instructions = field(form, 'Was soll CasaJev beachten?', skill.instructions || '', 'textarea');
  instructions.required = true;
  instructions.maxLength = 8000;
  const enabled = check(form, 'Diese Anleitung verwenden', skill.enabled ?? true);
  submit(form, 'Anleitung speichern', async () => {
    await api('/api/skills/save', {
      id: skill.id,
      name: name.value,
      description: description.value,
      instructions: instructions.value,
      enabled: enabled.checked,
    });
    await manage('extensions');
  });
  box.append(form);
  if (skill.id) {
    const remove = button('Anleitung löschen', async () => {
      await api('/api/skills/delete', { id: skill.id });
      await manage('extensions');
    }, 'danger');
    remove.style.marginTop = '16px';
    box.append(remove);
  }
}

function connectionStatus(value, fallback) {
  return {
    connected: 'Bereit',
    disconnected: 'Nicht angemeldet',
    unconfirmed: 'Noch nicht geprüft',
  }[value] || fallback;
}

function renderAccounts(box) {
  const accounts = manageData.accounts;
  box.append(node('p', 'Hier siehst du, welche Dienste CasaJev nutzen kann. Zugangsdaten bleiben auf diesem Gerät.', 'intro'));

  const layaAction = accounts.laya.active
    ? button('Prüfen', async () => {
      const result = await api('/api/accounts/check', { provider: 'laya' });
      await manage('accounts');
      notice(connectionStatus(result.status, 'Nicht bestätigt'));
    })
    : button('Einrichtung anzeigen', () => notice('Laya lokal starten: uv run casajev --policy laya serve'));

  box.append(row(
    'Laya · auf diesem Gerät',
    accounts.laya.active
      ? (accounts.laya.warmed ? 'Bereit · ' + accounts.laya.model : 'Eingerichtet · wird erst bei Bedarf geladen')
      : 'Optional für klar begrenzte Echtzeit-Aufgaben',
    [layaAction],
  ).element);

  box.append(row(
    'Jev · TypeSafe',
    accounts.jev.mode === 'demo'
      ? 'Simulation'
      : connectionStatus(accounts.jev.check, accounts.jev.configured ? 'Schlüssel hinterlegt · noch nicht geprüft' : 'Schlüssel fehlt'),
    [
      button('Prüfen', async () => {
        const result = await api('/api/accounts/check', { provider: 'jev' });
        await manage('accounts');
        notice(connectionStatus(result.status, 'Nicht bestätigt'));
      }),
      button('Schlüssel hinterlegen', () => jevEditor()),
    ],
  ).element);

  box.append(row(
    'GPT · Codex',
    connectionStatus(accounts.codex.check, accounts.codex.installed ? 'Codex gefunden · Anmeldung noch nicht geprüft' : 'Codex nicht gefunden'),
    [button('Anmeldung prüfen', async () => {
      const result = await api('/api/accounts/check', { provider: 'codex' });
      await manage('accounts');
      notice(connectionStatus(result.status, 'Nicht bestätigt'));
    })],
  ).element);

  const login = node('details');
  login.append(
    node('summary', 'Hilfe bei der Codex-Anmeldung'),
    node('p', 'CasaJev verwendet deine vorhandene Codex-CLI-Anmeldung. Falls nötig, im Terminal „codex login“ ausführen und danach hier prüfen.'),
  );
  box.append(login);

  box.append(sectionHeading('Weitere Verbindungen'));
  box.append(row(
    'Browser-Sitzung',
    accounts.browser.saved
      ? 'Auf diesem Gerät gespeichert'
      : (manageData.settings.remember_browser ? 'Wird beim Browsen gespeichert' : 'Speichern ist aus'),
    [button('Gespeicherte Sitzung löschen', async () => {
      await api('/api/browser/forget', {});
      pageInfo = null;
      $('screen').classList.add('hidden');
      $('browserblank').classList.remove('hidden');
      await manage('accounts');
      notice('Die gespeicherte Browser-Sitzung wurde gelöscht.');
    })],
  ).element);

  box.append(row(
    'MCP-Verbindungen',
    'Zusätzliche, von dir eingerichtete Datenquellen und Werkzeuge.',
    [button('Verbindung hinzufügen', () => connectorEditor())],
  ).element);
  for (const connector of manageData.connectors) {
    box.append(row(
      connector.name,
      (connector.enabled ? 'Aktiv' : 'Inaktiv') + ' · ' + (connector.allowed_tools?.length || 0) + ' freigegebene Werkzeuge',
      [button('Verwalten', () => connectorEditor(connector))],
    ).element);
  }
}

function jevEditor() {
  const box = modal('Jev verbinden');
  box.append(node('p', 'Der TypeSafe-Schlüssel wird nur auf diesem Gerät gespeichert und danach nicht mehr angezeigt.', 'intro'));
  const form = node('form');
  const key = field(form, 'TypeSafe-Schlüssel', '', 'password');
  key.autocomplete = 'new-password';
  key.required = true;
  submit(form, 'Schlüssel speichern', async () => {
    await api('/api/accounts/jev', { key: key.value });
    key.value = '';
    await manage('accounts');
  });
  box.append(form);
}

function connectorEditor(connector = {}) {
  const box = modal(connector.id ? connector.name : 'MCP-Verbindung hinzufügen');
  box.append(node('p', 'Richte nur vertrauenswürdige lokale Server ein. CasaJev gibt ausschließlich die hier ausgewählten lesenden Werkzeuge frei.', 'intro'));
  const form = node('form');
  const name = field(form, 'Name', connector.name || '');
  const command = field(form, 'Programm oder Pfad', connector.command || '');
  const args = field(form, 'Argumente als JSON-Liste', JSON.stringify(connector.args || []));
  const env = field(form, 'Zugangsdaten als JSON-Objekt', '', 'textarea', 'Leer lassen, um bereits gespeicherte Werte zu behalten.');
  name.required = command.required = true;
  env.placeholder = '{"SERVICE_API_KEY":"…"}';
  env.autocomplete = 'off';
  if (connector.env_names?.length) box.append(node('p', 'Hinterlegte Variablen: ' + connector.env_names.join(', '), 'platform-status'));
  submit(form, 'Verbindung speichern', async () => {
    const body = { id: connector.id, name: name.value, command: command.value, args: JSON.parse(args.value) };
    if (env.value.trim()) body.env = JSON.parse(env.value);
    else if (!connector.id) body.env = {};
    const saved = await api('/api/connectors/save', body);
    env.value = '';
    manageData = await api('/api/manage');
    connectorEditor(manageData.connectors.find(item => item.id === saved.id));
    notice('Gespeichert. Du kannst jetzt die verfügbaren Werkzeuge abrufen.');
  });
  box.append(form);
  if (!connector.id) return;

  const actions = node('div', undefined, 'actions');
  actions.style.marginTop = '18px';
  actions.append(
    button('Werkzeuge abrufen', async () => {
      notice('Verbindung wird geprüft …');
      const updated = await api('/api/connectors/inspect', { id: connector.id });
      connectorEditor(updated);
      notice('Katalog geladen. Wähle die lesenden Werkzeuge aus.');
    }),
    button('Verbindung löschen', async () => {
      await api('/api/connectors/delete', { id: connector.id });
      await manage('accounts');
    }, 'danger'),
  );
  box.append(actions);

  if (connector.tools?.length) {
    const select = node('form');
    const fields = connector.tools.map(tool => {
      const enabled = check(select, tool.name + (tool.supported ? '' : ' · nicht unterstützt'), connector.allowed_tools?.includes(tool.name));
      enabled.disabled = !tool.supported;
      details(select, tool.name + ' – Beschreibung', tool.description);
      return { field: enabled, name: tool.name };
    });
    const readOnly = check(select, 'Nur lesende Werkzeuge dieses vertrauenswürdigen Servers freigeben', connector.read_only || false);
    const enabled = check(select, 'Verbindung für Jev aktivieren', connector.enabled || false);
    submit(select, 'Auswahl übernehmen', async () => {
      await api('/api/connectors/save', {
        id: connector.id,
        allowed_tools: fields.filter(item => item.field.checked && !item.field.disabled).map(item => item.name),
        read_only: readOnly.checked,
        enabled: enabled.checked,
      });
      await manage('accounts');
    });
    box.append(select);
  }
}

const providerChoices = [
  ['jev', 'Jev · empfohlen für normale Aufgaben'],
  ['laya', 'Laya · lokal für begrenzte Abläufe'],
];

function providerFields(form, settings) {
  const group = node('section', undefined, 'provider-settings settings-card');
  group.append(node('h3', 'Wie CasaJev entscheidet'));
  const general = selectField(
    group,
    'Normale Aufgaben',
    settings.general_decision_provider,
    providerChoices,
    'Für Chat, Browser und Werkzeuge ist Jev die empfohlene Wahl.',
  );
  const realtime = selectField(
    group,
    'Schnelle Echtzeit-Aufgaben',
    settings.realtime_decision_provider,
    providerChoices,
    'Laya bleibt lokal und wird erst geladen, wenn es wirklich gebraucht wird.',
  );
  form.append(group);
  return { general, realtime };
}

function renderSettings(box) {
  box.append(node('p', 'Die empfohlenen Einstellungen passen für die meisten Menschen. Ändere nur, was du wirklich brauchst.', 'intro'));
  const settings = manageData.settings;
  const form = node('form');
  const providers = providerFields(form, settings);

  const privacy = node('section', undefined, 'settings-card');
  privacy.append(node('h3', 'Browser'));
  const remember = check(privacy, 'Meine Browser-Sitzung auf diesem Gerät speichern', settings.remember_browser);
  privacy.append(node('p', 'So bleiben Anmeldungen beim nächsten Start erhalten.'));
  form.append(privacy);

  const advanced = node('details', undefined, 'advanced-settings');
  advanced.append(node('summary', 'Technische Einstellungen'));
  const advancedBody = node('div', undefined, 'advanced-body');
  const fields = {};
  for (const [key, label] of [
    ['chat_model', 'Modell für Antworten'],
    ['builder_model', 'Modell für neue Werkzeuge'],
    ['escalation_model', 'Modell für schwierige Reparaturen'],
  ]) {
    fields[key] = field(advancedBody, label, settings[key]);
  }
  const grid = node('div', undefined, 'grid-two');
  advancedBody.append(grid);
  for (const [key, label, min, max] of [
    ['max_steps', 'Maximale Arbeitsschritte', 4, 100],
    ['max_seconds', 'Maximale Dauer in Sekunden', 30, 3600],
    ['max_tool_retries', 'Wiederholungen bei kurzen Fehlern', 0, 3],
  ]) {
    fields[key] = field(grid, label, settings[key], 'number');
    fields[key].min = min;
    fields[key].max = max;
    fields[key].required = true;
  }
  advanced.append(advancedBody);
  form.append(advanced);

  submit(form, 'Speichern', async () => {
    const data = {
      remember_browser: remember.checked,
      general_decision_provider: providers.general.value,
      realtime_decision_provider: providers.realtime.value,
    };
    for (const [key, value] of Object.entries(fields)) {
      data[key] = value.type === 'number' ? Number(value.value) : value.value;
    }
    await api('/api/settings', data);
    notice('Gespeichert. Die Änderung gilt für neue Arbeitsschritte.');
  });
  box.append(form);
}

function radioCards(form, name, title, value, choices) {
  const section = node('section', undefined, 'settings-card');
  section.append(node('h3', title));
  const grid = node('div', undefined, 'choice-grid');
  for (const choice of choices) {
    const label = node('label', undefined, 'choice-card');
    const input = node('input');
    input.type = 'radio';
    input.name = name;
    input.value = choice.id;
    input.checked = choice.id === value;
    input.setAttribute('aria-label', choice.title + ': ' + choice.description);
    label.append(input, node('strong', choice.title), node('small', choice.description));
    if (choice.badge) label.append(node('em', choice.badge));
    grid.append(label);
  }
  section.append(grid);
  form.append(section);
  return {
    get value() {
      return form.querySelector('input[name="' + name + '"]:checked').value;
    },
  };
}

function renderOnboarding(box) {
  const settings = manageData.settings;
  const platform = manageData.platform;
  box.append(node('p', 'Die sinnvolle Voreinstellung ist schon gewählt. Du kannst direkt loslegen und alles später ändern.', 'welcome-copy'));

  const recommendation = node('div', undefined, 'recommendation');
  recommendation.append(
    node('strong', 'Unsere Empfehlung'),
    node('span', 'Jev übernimmt normale Aufgaben. Laya bleibt für kleine Echtzeit-Abläufe lokal auf deinem Gerät.'),
  );
  box.append(recommendation);

  const form = node('form');
  const general = radioCards(form, 'general_provider', 'Normale Aufgaben', settings.general_decision_provider, [
    { id: 'jev', title: 'Jev', description: 'Die zuverlässigere Wahl für Chat, Browser und Werkzeuge.', badge: 'EMPFOHLEN' },
    { id: 'laya', title: 'Laya', description: 'Lokal und schnell, aber nur für klar begrenzte Abläufe.' },
  ]);
  const realtime = radioCards(form, 'realtime_provider', 'Echtzeit-Aufgaben', settings.realtime_decision_provider, [
    { id: 'laya', title: 'Laya', description: 'Läuft lokal und wird erst bei Bedarf geladen.', badge: 'EMPFOHLEN' },
    { id: 'jev', title: 'Jev', description: 'Für vielseitige Aufgaben, nicht auf Echtzeit optimiert.' },
  ]);

  const why = node('details');
  why.append(
    node('summary', 'Warum diese Auswahl?'),
    node('p', 'Jev blieb im allgemeinen Acht-Fälle-Test korrekt. Laya erreichte dort 1 von 8 Fällen, ist aber für vorher geprüfte kleine Aktionsräume gedacht.'),
  );
  why.querySelector('summary').setAttribute('aria-label', 'Warum diese Auswahl?');
  form.append(why);

  const technical = node('details');
  technical.append(
    node('summary', 'Technische Hinweise'),
    node(
      'p',
      (platform.laya_installed ? 'Laya ist lokal installiert.' : 'Laya ist noch nicht installiert und wird vor dem ersten Einsatz benötigt.')
        + ' · ' + platform.system + ' ' + platform.machine + ' · Worker: ' + platform.worker_backend,
      'platform-status',
    ),
  );
  technical.querySelector('summary').setAttribute('aria-label', 'Technische Hinweise');
  form.append(technical);

  submit(form, 'Mit CasaJev starten', async () => {
    await api('/api/onboarding', {
      general_decision_provider: general.value,
      realtime_decision_provider: realtime.value,
    });
    $('manageDialog').close();
    $('message').focus();
  });
  box.append(form);
}

api('/api/state').then(state => {
  if (state.onboarding_required) manage('onboarding');
}).catch(() => {});
