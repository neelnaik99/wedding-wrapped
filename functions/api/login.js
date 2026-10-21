// POST /api/login — the Login page posts an email here; see functions/_lib/login.js for the contract.
import map from "../_lib/login-map.json"
import { handleLogin } from "../_lib/login.js"
import { loginEmail } from "../_lib/email.js"

export function onRequestPost({ request, env, waitUntil }) {
  const send = async ({ to, greeting, url }) => {
    const { subject, html, text } = loginEmail({ greeting, url })
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: env.MAIL_FROM, to: [to], subject, html, text }),
    })
    if (!res.ok) throw new Error(`resend ${res.status}: ${await res.text()}`)
  }
  return handleLogin({ request, map, kv: env.LOGIN_KV, send, waitUntil, log: console.error })
}
