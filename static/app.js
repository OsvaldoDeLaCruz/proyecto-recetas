// Frontend mínimo: consume la API REST con el JWT guardado en localStorage.
const TOKEN_KEY = "recetas_token";
const $ = (sel) => document.querySelector(sel);
const DIFF_LABEL = { facil: "Fácil", media: "Media", dificil: "Difícil" };

function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
function setToken(t) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch {}
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 401 && token) {
    logout();
    throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = data.detail || `Error ${res.status}`;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg.replace(/^Value error, /, "")).join(". ");
    throw new Error(msg);
  }
  return data;
}

function showMsg(el, text, kind = "error") {
  el.textContent = text || "";
  el.className = `msg ${text ? kind : ""}`;
}

// ---------- Autenticación ----------
document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $("#login-form").classList.toggle("hidden", tab.dataset.tab !== "login");
    $("#register-form").classList.toggle("hidden", tab.dataset.tab !== "register");
    showMsg($("#auth-msg"), "");
  })
);

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const { access_token } = await api("/api/auth/login", {
      method: "POST",
      form: { username: fd.get("username"), password: fd.get("password") },
    });
    setToken(access_token);
    e.target.reset();
    await enterApp();
  } catch (err) {
    showMsg($("#auth-msg"), err.message);
  }
});

$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/api/auth/register", {
      method: "POST",
      body: { username: fd.get("username"), email: fd.get("email"), password: fd.get("password") },
    });
    const { access_token } = await api("/api/auth/login", {
      method: "POST",
      form: { username: fd.get("username"), password: fd.get("password") },
    });
    setToken(access_token);
    e.target.reset();
    await enterApp();
  } catch (err) {
    showMsg($("#auth-msg"), err.message);
  }
});

function logout() {
  setToken(null);
  $("#app-view").classList.add("hidden");
  $("#session").classList.add("hidden");
  $("#auth-view").classList.remove("hidden");
}
$("#logout").addEventListener("click", logout);

async function enterApp() {
  const me = await api("/api/auth/me");
  $("#whoami").textContent = `Hola, ${me.username}`;
  $("#auth-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  $("#session").classList.remove("hidden");
  await Promise.all([loadIngredients(), loadRecipes()]);
}

// ---------- Ingredientes ----------
function fmtQty(i) {
  if (i.quantity == null) return "";
  return `${i.quantity}${i.unit ? " " + i.unit : ""}`;
}

async function loadIngredients() {
  const items = await api("/api/ingredients");
  const list = $("#ingredient-list");
  list.innerHTML = "";
  $("#ingredient-empty").classList.toggle("hidden", items.length > 0);
  for (const it of items) list.appendChild(renderIngredient(it));
}

function renderIngredient(it) {
  const li = document.createElement("li");
  const name = document.createElement("span");
  name.className = "name";
  name.textContent = it.name;
  const qty = document.createElement("span");
  qty.className = "qty";
  qty.textContent = fmtQty(it);
  const edit = document.createElement("button");
  edit.className = "btn small ghost";
  edit.textContent = "Editar";
  const del = document.createElement("button");
  del.className = "btn small danger";
  del.textContent = "Eliminar";
  li.append(name, qty, edit, del);

  del.addEventListener("click", async () => {
    try {
      await api(`/api/ingredients/${it.id}`, { method: "DELETE" });
      await loadIngredients();
    } catch (err) { showMsg($("#ingredient-msg"), err.message); }
  });

  edit.addEventListener("click", () => {
    li.innerHTML = "";
    const n = Object.assign(document.createElement("input"), { value: it.name, className: "edit-name" });
    const q = Object.assign(document.createElement("input"), { value: it.quantity ?? "", type: "number", step: "any", min: "0", placeholder: "Cant." });
    const u = Object.assign(document.createElement("input"), { value: it.unit ?? "", placeholder: "Unidad" });
    const save = Object.assign(document.createElement("button"), { className: "btn small primary", textContent: "Guardar" });
    const cancel = Object.assign(document.createElement("button"), { className: "btn small ghost", textContent: "Cancelar" });
    li.append(n, q, u, save, cancel);
    cancel.addEventListener("click", loadIngredients);
    save.addEventListener("click", async () => {
      try {
        await api(`/api/ingredients/${it.id}`, {
          method: "PATCH",
          body: { name: n.value, quantity: q.value ? Number(q.value) : null, unit: u.value || null },
        });
        showMsg($("#ingredient-msg"), "Ingrediente actualizado", "ok");
        await loadIngredients();
      } catch (err) { showMsg($("#ingredient-msg"), err.message); }
    });
  });
  return li;
}

$("#ingredient-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const quantity = fd.get("quantity");
  try {
    await api("/api/ingredients", {
      method: "POST",
      body: { name: fd.get("name"), quantity: quantity ? Number(quantity) : null, unit: fd.get("unit") || null },
    });
    e.target.reset();
    showMsg($("#ingredient-msg"), "");
    await loadIngredients();
  } catch (err) { showMsg($("#ingredient-msg"), err.message); }
});

// ---------- Recetas ----------
function renderRecipe(r) {
  const node = $("#recipe-template").content.firstElementChild.cloneNode(true);
  node.dataset.id = r.id;
  node.querySelector(".r-title").textContent = r.title;
  const meta = node.querySelector(".r-meta");
  const pills = [
    [`⏱ ${r.prep_time_minutes} min`, ""],
    [DIFF_LABEL[r.difficulty] || r.difficulty, r.difficulty],
    [r.servings ? `${r.servings} porciones` : "", ""],
    [new Date(r.created_at).toLocaleString("es-CO"), ""],
  ];
  for (const [text, cls] of pills) {
    if (!text) continue;
    const s = document.createElement("span");
    s.className = `pill ${cls}`;
    s.textContent = text;
    meta.appendChild(s);
  }
  const ul = node.querySelector(".r-ingredients");
  for (const i of r.ingredients) {
    const li = document.createElement("li");
    li.textContent = `${i.nombre}: ${i.cantidad}`;
    ul.appendChild(li);
  }
  const ol = node.querySelector(".r-steps");
  for (const step of r.steps) {
    const li = document.createElement("li");
    li.textContent = step;
    ol.appendChild(li);
  }
  const stars = node.querySelector(".stars");
  for (let n = 1; n <= 5; n++) {
    const b = document.createElement("button");
    b.textContent = "★";
    b.title = `${n} estrella${n > 1 ? "s" : ""}`;
    b.setAttribute("aria-label", b.title);
    b.classList.toggle("on", r.rating != null && n <= r.rating);
    b.addEventListener("click", async () => {
      try {
        await api(`/api/recipes/${r.id}/rating`, { method: "PUT", body: { score: n } });
        r.rating = n;
        // Actualiza todas las tarjetas de esta receta (la recién generada y la del historial).
        document.querySelectorAll(`.recipe[data-id="${r.id}"] .stars button`).forEach((x, idx) =>
          x.classList.toggle("on", idx < n)
        );
      } catch (err) { alert(err.message); }
    });
    stars.appendChild(b);
  }
  node.querySelector(".r-delete").addEventListener("click", async () => {
    if (!confirm(`¿Eliminar "${r.title}" del historial?`)) return;
    try {
      await api(`/api/recipes/${r.id}`, { method: "DELETE" });
      await loadRecipes();
      const gen = $("#generated");
      if (gen.dataset.id === String(r.id)) { gen.innerHTML = ""; delete gen.dataset.id; }
    } catch (err) { alert(err.message); }
  });
  return node;
}

async function loadRecipes() {
  const diff = $("#filter-difficulty").value;
  const recipes = await api(`/api/recipes${diff ? `?difficulty=${diff}` : ""}`);
  const list = $("#recipe-list");
  list.innerHTML = "";
  $("#recipe-empty").classList.toggle("hidden", recipes.length > 0);
  for (const r of recipes) list.appendChild(renderRecipe(r));
}
$("#filter-difficulty").addEventListener("change", loadRecipes);

$("#generate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const btn = $("#generate-btn");
  btn.disabled = true;
  btn.textContent = "Generando…";
  showMsg($("#generate-msg"), "La IA está preparando tu receta, puede tardar unos segundos.", "ok");
  try {
    const recipe = await api("/api/recipes/generate", {
      method: "POST",
      body: { meal_type: fd.get("meal_type") || null, servings: Number(fd.get("servings") || 2) },
    });
    const gen = $("#generated");
    gen.innerHTML = "";
    gen.dataset.id = recipe.id;
    gen.appendChild(renderRecipe(recipe));
    showMsg($("#generate-msg"), "Receta generada y guardada en tu historial.", "ok");
    await loadRecipes();
  } catch (err) {
    showMsg($("#generate-msg"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generar con IA";
  }
});

// ---------- Inicio ----------
if (getToken()) enterApp().catch(logout);
