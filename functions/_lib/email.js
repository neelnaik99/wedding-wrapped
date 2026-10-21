// The Login email: one greeting, one button to the Household's Link. Palette matches make_emails.py.

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])

export function loginEmail({ greeting, url }) {
  const text = `Hi ${greeting},\n\nThank you for celebrating with us in Atlanta! We went through all the wedding photos and put together the ones of you:\n${url}\n\nWe hope they make you smile.\n\nWith love,\nPreethi & Neel`
  const html = `<div style="font-family:Georgia,serif;max-width:520px">
<p>Hi ${esc(greeting)},</p>
<p>Thank you for celebrating with us in Atlanta! We went through all the wedding photos and put together the ones of you:</p>
<p style="margin:22px 0"><a href="${esc(url)}" style="background:#b8862b;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;display:inline-block">Open your Wedding Wrapped</a></p>
<p>We hope they make you smile.</p>
<p>With love,<br>Preethi &amp; Neel</p></div>`
  return { subject: "Your Wedding Wrapped link", text, html }
}
