import { test } from "node:test"
import assert from "node:assert/strict"
import { loginEmail } from "../../functions/_lib/email.js"

const m = loginEmail({ greeting: "Avery & Simon", url: "https://w.dev/h/tok/" })

test("subject is fixed", () => {
  assert.equal(m.subject, "Your Wedding Wrapped link")
})

test("text body greets, links, signs off", () => {
  assert.equal(m.text, "Hi Avery & Simon,\n\nThank you for celebrating with us in Atlanta! We went through all the wedding photos and put together the ones of you:\nhttps://w.dev/h/tok/\n\nWe hope they make you smile.\n\nWith love,\nPreethi & Neel")
})

test("html has one button to the Link and an escaped greeting", () => {
  assert.match(m.html, /Hi Avery &amp; Simon,/)
  assert.match(m.html, /Thank you for celebrating with us in Atlanta!/)
  assert.match(m.html, /We hope they make you smile\./)
  assert.equal(m.html.match(/<a /g).length, 1)
  assert.match(m.html, /href="https:\/\/w\.dev\/h\/tok\/"[^>]*>Open your Wedding Wrapped</)
})

test("greeting cannot inject markup", () => {
  const x = loginEmail({ greeting: '<img src=x onerror=alert(1)>', url: "https://w.dev/d/" })
  assert.ok(!x.html.includes("<img"))
})
