// Presentation-only localisation: never translate or mutate student facts or model claims.
let language = 'en';
try { language = localStorage.getItem('counselor.language') === 'zh' ? 'zh' : 'en'; } catch {}
const choose = (zh, en) => language === 'zh' ? zh : en;
const ELEMENTS_EN = {process:"Process", knowledge:"Knowledge used", problem:"Problem", solution:"Solution", reflection:"Reflection", outcome:"Outcome"};
const TEXT_EN = {
  "申请主线":"Application theme", "UCAS 三问写作思路":"Approach to the three UCAS questions",
  "经历与素材说明":"Experiences and writing material", "待向学生确认":"Questions for the student",
  "收尾核查":"Final review", "专业认知":"Understanding of the subject", "经历与专业的结合":"Connection to the subject", "成长轨迹":"Development over time",
  "论点措辞与事实核查":"Claim wording and evidence review", "有事实支持":"Supported by evidence",
  "收窄后有事实支持":"Supported after narrowing", "表述过强":"Overstated", "证据不足":"Insufficient evidence",
  "与记录冲突":"Conflicts with the record", "仅有简历记录，待学生确认":"CV record only; needs student confirmation",
  "数字缺少对应依据":"Numbers lack matching evidence", "事实引用无效":"Invalid evidence reference",
  "核查未完成":"Review incomplete", "论点未完整拆分":"Incomplete claim segmentation",
  "请求失败":"Request failed", "JSON 文件无法解析":"Unable to parse the JSON file",
  "文件不能超过 5 MB":"The file must be no larger than 5 MB", "读取文件失败":"Unable to read the file",
  "至少选择一个目标项目":"Select at least one target programme", "请先选择档案文件":"Choose a profile file first",
  "请输入回答，或点击跳过":"Enter an answer or skip the question", "单轮回答最多 3000 字":"Each answer must be no longer than 3,000 characters",
  "会话已失效，请重新开始":"The session has expired. Please start a new case.",
  "结果已生成；请重新开始新的案例":"The result has been generated. Please start a new case.",
  "这是头脑风暴素材包，不是个人陈述成稿；待探讨内容不得写成学生事实。":"This is a brainstorming brief, not a finished personal statement. Topics for further discussion must not be presented as student facts.",
  "从学生已记录的经历与反思出发，解释与计算机科学的关系。":"Explain the connection to Computer Science using the student's recorded experiences and reflections.",
  "当前证据不足，先补充相应经历与思考。":"There is not enough evidence yet. Collect relevant experiences and reflections first.",
  "候选主线：从已记录的经历中寻找对计算机科学的具体兴趣与持续探索":"Possible theme: identify specific interests in Computer Science and continued exploration in the recorded experiences.",
  "已有至少一段本人反思或专业问题说明；需核对其学术准确性。":"At least one reflection or explanation of a subject question is recorded; check its academic accuracy.",
  "尚缺学生本人对计算机科学问题的具体理解。":"The student's specific understanding of Computer Science questions is still missing.",
  "至少一段经历具备可指认的知识、方法或兴趣匹配；仍需核对相关性。":"At least one experience has an identifiable connection through knowledge, methods or interests; check its relevance.",
  "经历与目标专业的具体连接尚未建立。":"A specific connection between the experiences and the target subject has not been established.",
  "多段经历均记录了个人反思；可进一步核对真实的递进关系。":"Several experiences include reflections; check whether they show genuine development.",
  "尚不足以确认从探索到深化的递进轨迹。":"There is not enough evidence to confirm development from exploration to deeper understanding.",
  "细节尚未经过充分追问":"The details have not been explored sufficiently", "仍有六要素空缺":"Some of the six experience dimensions are still missing",
  "行为过程":"Process", "运用知识":"Knowledge used", "遇到的问题":"Problem", "解决方法":"Solution", "个人思考":"Reflection", "最终收获":"Outcome", "专业深挖":"Subject exploration",
};
function fixed(text) { return language === 'en' ? (TEXT_EN[text] || text) : text; }
function listText(items) { return items.join(choose('、', ', ')); }
function questionText(data) {
  const q = data.question;
  if (!q) return choose('已完成可用的追问，可以生成素材包。', 'The available questions are complete. You can generate the brief.');
  if (language === 'zh') return q.text;
  const title = q.experience_title;
  const problem = data.records.find(record => record.experience_id === q.experience_id)?.values.problem;
  const prompts = {
    process:`For “${title}”, what did you personally do from start to finish?`,
    knowledge:`What knowledge or skills did you use in “${title}”, and where did you apply them?`,
    problem:`What was one specific difficulty in “${title}”? Where did you get stuck?`,
    solution:problem ? `You mentioned “${problem.slice(0, 75)}”. What approaches did you try, and why did you choose the final one?` : `Was there a key step in “${title}” that you worked out yourself? What did you do, and why?`,
    reflection:`After “${title}”, what new questions or ideas did you have about Computer Science?`,
    outcome:`What identifiable work, code, report or other result came out of “${title}”?`,
    'deep:concept':`For “${title}”, which specific Computer Science problem does your method relate to? How do you understand it?`,
    'deep:alternative':`Looking back at “${title}”, what other options did you have? How did you compare them?`,
    'deep:limit':`For “${title}”, under what conditions might your approach fail? What would you like to learn to improve it?`,
  };
  return prompts[q.element] || q.text;
}
function angleText(material) {
  if (language === 'zh') return material.angle;
  if (material.angle === `探讨「${material.title}」中本人采取的做法及其思考`) return `Explore the student's own actions and reflections in “${material.title}”`;
  if (material.angle === `「${material.title}」仍需补充具体经历`) return `More specific details are needed for “${material.title}”`;
  return material.angle; // A model claim is evidence content, not interface copy.
}
function openQuestionText(text) {
  if (language === 'zh') return text;
  const match = /^关于「(.+)」：请补充(.+)。$/.exec(text);
  return match ? `For “${match[1]}”, please add: ${listText(match[2].split('、').map(fixed))}.` : text;
}
let displayedError = '';
let requestPending = false;
function applyLanguage() {
  document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN';
  document.title = choose('Academic Compass | 英国本科 CS 头脑风暴', 'Academic Compass | UK CS Brainstorming');
  document.querySelectorAll('[data-zh][data-en]').forEach(el => { el.textContent = el.dataset[language]; });
  $('languageToggle').textContent = choose('English', '中文');
  $('languageToggle').setAttribute('aria-label', choose('Switch to English', '切换到中文'));
  $('answer').placeholder = choose('尽量说清当时的场景、本人做法、选择依据与结果。', 'Describe the context, your own actions, reasons for your choices, and the result.');
  updateFileName();
  if (result) renderResult(result);
  else if (current) renderInterview(current, true);
  $('error').textContent = fixed(displayedError);
}
function updateFileName() {
  $('cvFileName').textContent = $('cvFile').files[0]?.name || choose('未选择文件', 'No file selected');
}
const $ = id => document.getElementById(id);
const ELEMENTS = {process:"行为过程", knowledge:"运用知识", problem:"遇到的问题", solution:"解决方法", reflection:"个人思考", outcome:"最终收获"};
let current = null;
let result = null;

function node(tag, content="", className="") {
  const el = document.createElement(tag);
  el.textContent = content;
  if (className) el.className = className;
  return el;
}
function clear(el) { el.replaceChildren(); }
function showError(error) { displayedError = error ? String(error.message || error) : ""; $("error").textContent = fixed(displayedError); }
async function api(path, body) {
  requestPending = true;
  try {
    const response = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");
    return data;
  } finally {
    requestPending = false;
  }
}
function selectedProgrammes() {
  return [...document.querySelectorAll('#programmes input:checked')].map(el => el.value);
}
async function filePayload(file) {
  if (file.name.toLowerCase().endsWith('.json')) {
    try { return {cv: JSON.parse(await file.text())}; }
    catch { throw new Error("JSON 文件无法解析"); }
  }
  if (file.size > 5_000_000) throw new Error("文件不能超过 5 MB");
  const base64 = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
  return {file:{name:file.name, content_base64:base64}};
}
function renderInterview(data, preserveDraft = false) {
  current = data;
  $("startPanel").classList.add("hidden");
  $("resultPanel").classList.add("hidden");
  $("interviewPanel").classList.remove("hidden");
  if (!preserveDraft) $("answer").value = "";
  $("progress").textContent = choose(`第 ${data.round} 轮 · 信息覆盖 ${Math.round(data.progress * 100)}%`, `Round ${data.round} · Field coverage ${Math.round(data.progress * 100)}%`);
  $("caseSummary").textContent = `${data.student} · ${data.records.length} ${choose("段经历", "experiences")} · ${listText(data.programmes.map(p => p.university))}`;
  $("question").textContent = questionText(data);
  $("why").textContent = data.question ? choose(`提问原因：${data.question.why}`, `Why this question: ${data.question.element.startsWith("deep:") ? "Connect the experience to specific Computer Science questions." : `The ${ELEMENTS_EN[data.question.element] || data.question.element} dimension needs the student's own explanation.`}`) : "";
  $("submit").disabled = requestPending || !data.question;
  $("skip").disabled = requestPending || !data.question;
  $("finish").disabled = requestPending;
  const container = $("records"); clear(container);
  for (const record of data.records) {
    const section = node("section", "", "block");
    section.append(node("h2", record.title));
    for (const [key, label] of Object.entries(ELEMENTS)) {
      const row = node("div", "", "row");
      row.append(node("b", fixed(label)), node("span", record.values[key] || choose("尚未获得", "Not yet recorded")));
      if (record.sources[key]) row.append(node("small", record.sources[key], "source"));
      section.append(row);
    }
    container.append(section);
  }
}
function renderResult(data) {
  result = data;
  $("interviewPanel").classList.add("hidden");
  $("startPanel").classList.add("hidden");
  $("resultPanel").classList.remove("hidden");
  const root = $("resultContent"); clear(root);
  root.append(node("h2", data.student), node("p", fixed(data.notice), "notice"));
  const thesis = node("section", "", "block");
  thesis.append(node("h2", fixed("申请主线")), node("p", fixed(data.thesis_claim)));
  root.append(thesis);
  const sections = node("section", "", "block");
  sections.append(node("h2", fixed("UCAS 三问写作思路")));
  for (const section of data.sections) {
    sections.append(node("h3", choose(section.question, section.question_en || section.question)), node("p", fixed(section.strategy)));
    const titles = data.materials.filter(m => section.material_ids.includes(m.id)).map(m => m.title);
    if (titles.length) sections.append(node("p", `${choose("关联素材：", "Related material: ")}${listText(titles)}`, "muted"));
  }
  root.append(sections);
  const mats = node("section", "", "block"); mats.append(node("h2", fixed("经历与素材说明")));
  for (const mat of data.materials) {
    const section = node("section", "", "material-card");
    section.append(node("h3", mat.title), node("p", `${choose("状态：", "Status: ")}${materialStatus(mat.status)} · ${listText((mat.match_labels || []).map(matchLabel)) || choose("待匹配", "No match yet")}`, "muted"));
    section.append(node("p", `${choose("写作角度：", "Writing angle: ")}${angleText(mat)}`));
    section.append(node("p", (language === "en" && mat.evidence?.length ? mat.evidence.map(fact => `${fixed(fact.label)}: ${fact.text}`).join(". ") : mat.narrative) || choose("尚无可确认的经历细节。", "No experience details are available for confirmation yet.")));
    section.append(node("p", language === "en" && mat.guide_note === `适合围绕${mat.angle}与学生继续核实。写作时只使用上方已记录的事实；空缺项留待追问。` ? `Continue checking this angle with the student: ${angleText(mat)}. Use only recorded facts; ask about missing details.` : mat.guide_note, "muted"));
    section.append(node("p", language === "en" && mat.usage === `可作为 ${mat.prompt_id} 的候选素材；按学生能讲清的细节决定篇幅。` ? `Candidate material for ${mat.prompt_id}; decide its length based on the details the student can explain.` : mat.usage, "muted"));
    if (mat.pairing) section.append(node("p", `${choose("可串联经历：", "Related experience: ")}${mat.pairing}`, "muted"));
    for (const caveat of mat.caveats || []) section.append(node("p", fixed(caveat), "notice"));
    if (mat.key_points.length) {
      const list = node("ul");
      for (const item of mat.key_points) list.append(node("li", pointText(item)));
      section.append(list);
    }
    if (mat.missing.length) section.append(node("p", `${choose("仍需补充：", "Still needed: ")}${listText(mat.missing.map(fixed))}`, "notice"));
    const sources = [...new Set(mat.evidence.map(item => item.source).filter(Boolean))];
    if (sources.length) section.append(node("small", `${choose("来源：", "Sources: ")}${listText(sources)}`, "source"));
    mats.append(section);
  }
  root.append(mats);
  if (data.open_questions.length) {
    const section = node("section", "", "block"); section.append(node("h2", fixed("待向学生确认")));
    const list = node("ul");
    for (const question of data.open_questions) list.append(node("li", openQuestionText(question)));
    section.append(list); root.append(section);
  }
  const checks = node("section", "", "block"); checks.append(node("h2", fixed("收尾核查")));
  for (const [label, key] of [["专业认知","professional_cognition"],["经历与专业的结合","connection"],["成长轨迹","growth"]]) {
    checks.append(node("p", `${fixed(label)}: ${fixed(data.checks[key])}`));
  }
  root.append(checks);
  if (data.claim_audit?.length) {
    const audit = node("section", "", "block");
    audit.append(node("h2", fixed("论点措辞与事实核查")));
    const labels = {supported:"有事实支持", narrowed_supported:"收窄后有事实支持",
      overstated:"表述过强", insufficient:"证据不足", contradicted:"与记录冲突",
      needs_confirmation:"仅有简历记录，待学生确认", unsupported_measurement:"数字缺少对应依据",
      invalid_reference:"事实引用无效", review_missing:"核查未完成",
      incomplete_segmentation:"论点未完整拆分"};
    for (const claim of data.claim_audit) {
      const block = node("section", "", "material-card");
      block.append(node("h3", claim.claim), node("p", `${choose("判定：", "Verdict: ")}${fixed(labels[claim.status] || claim.status)}`));
      if (claim.accepted_wording) block.append(node("p", `${choose("可用措辞：", "Accepted wording: ")}${claim.accepted_wording}`));
      else if (claim.suggested_wording) block.append(node("p", `${choose("待核查的收窄建议：", "Narrower wording awaiting review: ")}${claim.suggested_wording}`, "notice"));
      for (const part of claim.segments) {
        block.append(node("p", `${part.text} · ${fixed(labels[part.status] || part.status)}`));
        for (const fact of part.evidence) block.append(node("small", `${choose("依据：", "Evidence: ")}${fact.quote} (${fact.source})`, "source"));
      }
      audit.append(block);
    }
    root.append(audit);
  }
}
async function start(useDemo) {
  try {
    showError(null);
    const program_ids = selectedProgrammes();
    if (!program_ids.length) throw new Error("至少选择一个目标项目");
    const payload = {program_ids};
    if (!useDemo) {
      const file = $("cvFile").files[0];
      if (!file) throw new Error("请先选择档案文件");
      Object.assign(payload, await filePayload(file));
    }
    $("startUploaded").disabled = $("startDemo").disabled = true;
    renderInterview(await api("/api/full/start", payload));
  } catch (error) { showError(error); }
  finally { $("startUploaded").disabled = $("startDemo").disabled = false; }
}
async function answer(value) {
  try {
    showError(null);
    $("submit").disabled = $("skip").disabled = true;
    renderInterview(await api("/api/full/answer", {session_id:current.session_id, answer:value}));
  } catch (error) { showError(error); }
  finally { if (current?.question) $("submit").disabled = $("skip").disabled = false; }
}
async function finish() {
  try {
    showError(null); $("finish").disabled = true;
    renderResult(await api("/api/full/finish", {session_id:current.session_id}));
  } catch (error) { showError(error); }
  finally { $("finish").disabled = false; }
}
$("startUploaded").onclick = () => start(false);
$("startDemo").onclick = () => start(true);
$("submit").onclick = () => answer($("answer").value);
$("skip").onclick = () => answer("[跳过]");
$("finish").onclick = finish;
$("download").onclick = () => { if (current && result) window.location.href = `/api/full/export/${encodeURIComponent(current.session_id)}`; };
$("restart").onclick = () => {current=null; result=null; $("resultPanel").classList.add("hidden"); $("startPanel").classList.remove("hidden"); showError(null);};
fetch("/api/programmes").then(response => response.json()).then(data => {
  const root = $("programmes"); clear(root);
  for (const programme of data.programmes) {
    const label = node("label", "", "programme-option");
    const input = document.createElement("input"); input.type="checkbox"; input.value=programme.id;
    if (!root.childElementCount) input.checked=true;
    label.append(input, node("span", `${programme.university} · ${programme.name}`));
    root.append(label);
  }
}).catch(showError);

function materialStatus(status) {
  const names = {core_usable: ['核心素材候选', 'Core material candidate'], needs_substantiation: ['仍需补充证据', 'Needs substantiation'], supplementary_usable: ['补充素材候选', 'Supplementary material candidate']};
  return names[status] ? choose(...names[status]) : status;
}
function matchLabel(label) {
  const names = {'技能与知识匹配':'Skills and knowledge', '思维与场景匹配':'Thinking and context', '志趣与方向匹配':'Interests and direction'};
  return language === 'en' ? (names[label] || label) : label;
}
function pointText(text) {
  if (language === 'zh') return text;
  const colon = text.indexOf('：');
  return colon >= 0 && TEXT_EN[text.slice(0, colon)] ? `${fixed(text.slice(0, colon))}: ${text.slice(colon + 1)}` : text;
}
$('languageToggle').onclick = () => {
  language = language === 'en' ? 'zh' : 'en';
  try { localStorage.setItem('counselor.language', language); } catch {}
  applyLanguage();
};
$('cvFile').addEventListener('change', updateFileName);
applyLanguage();
