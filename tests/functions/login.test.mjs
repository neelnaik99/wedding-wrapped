import { test } from "node:test"
import assert from "node:assert/strict"
import { handleLogin, NEUTRAL } from "../../functions/_lib/login.js"

const MAP = { "sydney@gmail.com": { url: "https://w.dev/h/tok/", greeting: "Sydney & Jordan" } }

function req(body) {
  return new Request("https://w.dev/api/login", { method: "POST", body: typeof body === "string" ? body : JSON.stringify(body) })
}

// Fakes for the injected world: an in-memory KV, a recording send, a waitUntil that collects work.
function world({ send } = {}) {
  const store = new Map(), sent = [], pending = [], logs = []
  return {
    store, sent, pending, logs,
    kv: { get: async (k) => store.get(k) ?? null, put: async (k, v, o) => { store.set(k, v); store.lastTtl = o?.expirationTtl }, delete: async (k) => { store.delete(k) } },
    send: send ?? (async (m) => { sent.push(m) }),
    waitUntil: (p) => { pending.push(p) },
    log: (...a) => logs.push(a),
  }
}

async function run(w, body) {
  const res = await handleLogin({ request: req(body), map: MAP, kv: w.kv, send: w.send, waitUntil: w.waitUntil, log: w.log })
  await Promise.allSettled(w.pending)
  return res
}

test("known email → 200 neutral, send called once with to/greeting/url", async () => {
  const w = world()
  const res = await run(w, { email: "sydney@gmail.com" })
  assert.equal(res.status, 200)
  assert.deepEqual(await res.json(), { ok: true, message: NEUTRAL })
  assert.deepEqual(w.sent, [{ to: "sydney@gmail.com", greeting: "Sydney & Jordan", url: "https://w.dev/h/tok/" }])
})

test("unknown email → 200 identical body, send never called", async () => {
  const w = world()
  const res = await run(w, { email: "stranger@example.com" })
  assert.equal(res.status, 200)
  assert.deepEqual(await res.json(), { ok: true, message: NEUTRAL })
  assert.equal(w.sent.length, 0)
})

test("mixed case and spaces still match", async () => {
  const w = world()
  await run(w, { email: "  Sydney@GMAIL.com " })
  assert.equal(w.sent.length, 1)
  assert.equal(w.sent[0].to, "sydney@gmail.com")
})

test("responds before send settles", async () => {
  const w = world({ send: () => new Promise(() => {}) })   // never resolves
  const res = await handleLogin({ request: req({ email: "sydney@gmail.com" }), map: MAP, kv: w.kv, send: w.send, waitUntil: w.waitUntil, log: w.log })
  assert.equal(res.status, 200)
  assert.equal(w.pending.length, 1)
})

test("second request inside the cooldown → neutral, no second send", async () => {
  const w = world()
  await run(w, { email: "sydney@gmail.com" })
  const res = await run(w, { email: "sydney@gmail.com" })
  assert.deepEqual(await res.json(), { ok: true, message: NEUTRAL })
  assert.equal(w.sent.length, 1)
  assert.equal(w.store.lastTtl, 600)
  assert.ok([...w.store.keys()].every((k) => k.startsWith("cd:") && !k.includes("sydney")), "KV keys must not hold the raw address")
})

test("send throws → neutral, cooldown not set, error logged", async () => {
  const w = world({ send: async () => { throw new Error("resend 500") } })
  const res = await run(w, { email: "sydney@gmail.com" })
  assert.deepEqual(await res.json(), { ok: true, message: NEUTRAL })
  assert.equal(w.store.size, 0)
  assert.equal(w.logs.length, 1)
})

test("malformed JSON → 400", async () => {
  const res = await run(world(), "{not json")
  assert.equal(res.status, 400)
})

test("no @ in email → 400", async () => {
  const res = await run(world(), { email: "sydney" })
  assert.equal(res.status, 400)
})

test("concurrent requests for one address send once", async () => {
  let release
  const gate = new Promise((r) => { release = r })
  const w = world({ send: async (m) => { await gate; w.sent.push(m) } })
  const call = () => handleLogin({ request: req({ email: "sydney@gmail.com" }), map: MAP, kv: w.kv, send: w.send, waitUntil: w.waitUntil, log: w.log })
  await Promise.all([call(), call(), call()])
  await new Promise((r) => setTimeout(r, 50))   // let every request get past its async hash + KV read
  release()
  await Promise.allSettled(w.pending)
  assert.equal(w.sent.length, 1)
})

test("KV failure is logged, guest still gets the neutral answer", async () => {
  const w = world()
  w.kv.get = async () => { throw new Error("kv down") }
  const res = await run(w, { email: "sydney@gmail.com" })
  assert.equal(res.status, 200)
  assert.equal(w.logs.length, 1)
})
