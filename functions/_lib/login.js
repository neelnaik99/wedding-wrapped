// Login request logic — pure, every side effect injected, so it is tested without Workers.
// Contract (docs/adr/0001-login-mails-existing-links.md): every well-formed request gets the
// same answer at the same speed, known address or not; the Login email goes out in waitUntil.

export const NEUTRAL = "If we have that email, your link is on its way."
const COOLDOWN_S = 600   // one Login email per address per 10 minutes

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })

async function cooldownKey(email) {
  // hashed so KV never holds a guest's raw address
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email))
  return "cd:" + [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("")
}

export async function handleLogin({ request, map, kv, send, waitUntil, log }) {
  let email
  try {
    email = String((await request.json()).email ?? "").trim().toLowerCase()
  } catch {
    return json(400, { ok: false })
  }
  if (!email.includes("@")) return json(400, { ok: false })

  const entry = map[email]
  if (entry) {
    waitUntil((async () => {
      const key = await cooldownKey(email)
      let claimed = false
      try {
        if (await kv.get(key)) return
        // claim the cooldown before sending, so a burst of requests sends once
        await kv.put(key, "1", { expirationTtl: COOLDOWN_S })
        claimed = true
        await send({ to: email, greeting: entry.greeting, url: entry.url })
      } catch (e) {
        log("login failed", e?.message ?? e)
        if (claimed) await kv.delete(key).catch(() => {})   // nothing went out: a retry should work
      }
    })())
  }
  return json(200, { ok: true, message: NEUTRAL })
}
