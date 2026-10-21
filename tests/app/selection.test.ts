import test from "node:test"
import assert from "node:assert/strict"
import { cleanSel, mergePools, readHash, toggle, viewFor, writeHash } from "../../app/src/lib/selection.ts"

const shot = (url: string, who: number[], time = "10:00 AM") => ({
  url, thumbs: [], n_alt: 0, time, portrait: false, who,
})
const costar = (cid: number, n: number) => ({ cid, n, name: "c" + cid, img: "", labeled: true })
const ev = (name: string, n: number) => ({ key: name.toUpperCase(), name, n, first: "", last: "", day: "", pct: 0 })
const gmap = (tag: string, who: number[]) => ({
  name: tag, me: who[0], members: [], edges: [], rings: [], ringR: [], W: 1, H: 1, viewR: 1,
  photos: [{ id: tag + "1", s: "", l: "", gallery: "X", mem: [], who }],
})

function wrapped(cid: number, name: string, n: number, over: Record<string, unknown> = {}) {
  return {
    name, slug: "s" + cid, cluster: cid, hero: "hero" + cid, n_photos: n, n_events: 1, n_scenes: 1, n_hidden: 0,
    peak: ev("Haldi", n), events: [ev("Haldi", n)], costars: [], moments: [], gallery: [],
    picks: ["couple-pick"], couple: "C", dates: "D", gallery_link: "", from_us: null, ...over,
  }
}

function household(over: Record<string, any> = {}) {
  const a = { cid: 1, first: "Ann", light: false, wrapped: wrapped(1, "Ann", 100, over.a) }
  const b = { cid: 2, first: "Bob", light: false, wrapped: wrapped(2, "Bob", 50, over.b) }
  return {
    title: "Ann & Bob", couple: [15, 50], members: [a, b],
    summary: {
      "1": { n_photos: 100, n_events: 3, events: [ev("Haldi", 10), ev("Sangeet", 30)] },
      "2": { n_photos: 50, n_events: 2, events: [ev("Haldi", 5)] },
      "1,2": { n_photos: 140, n_events: 4, events: [ev("Haldi", 20)] },
    },
  } as any
}

test("toggle never empties", () => {
  assert.deepEqual(toggle([1], 1), [1])
  assert.deepEqual(toggle([1, 2], 1), [2])
  assert.deepEqual(toggle([1], 2), [1, 2])
})

test("all selected uses household title", () => {
  const h = household()
  assert.equal(viewFor(h, [1, 2]).name, "Ann & Bob")
  assert.equal(viewFor(h, [2]).name, "Bob")
})

test("shot only of an unselected member is hidden", () => {
  const g = [{ name: "Haldi", n_all: 2, shots: [shot("a", [1]), shot("b", [2])] }]
  const h = household({ a: { gallery: g }, b: { gallery: g } })
  const urls = viewFor(h, [1]).gallery[0].shots.map((s) => s.url)
  assert.deepEqual(urls, ["a"])
})

test("shared shot ranks above solo shots", () => {
  const g = [{ name: "Haldi", n_all: 3, shots: [shot("solo1", [1], "9:00 AM"), shot("both", [1, 2], "11:00 AM"), shot("solo2", [2], "8:00 AM")] }]
  const h = household({ a: { gallery: g } })
  const urls = viewFor(h, [1, 2]).gallery[0].shots.map((s) => s.url)
  assert.deepEqual(urls, ["both", "solo2", "solo1"])
})

test("same url from two members appears once", () => {
  const h = household({
    a: { gallery: [{ name: "Haldi", n_all: 1, shots: [shot("x", [1, 2])] }] },
    b: { gallery: [{ name: "Haldi", n_all: 1, shots: [shot("x", [1, 2])] }] },
  })
  assert.equal(viewFor(h, [1, 2]).gallery[0].shots.length, 1)
})

test("costars exclude household members", () => {
  const h = household({
    a: { costars: [costar(2, 9), costar(7, 3), costar(8, 1)] },
    b: { costars: [costar(1, 9), costar(7, 5)] },
  })
  const cs = viewFor(h, [1, 2]).costars
  assert.deepEqual(cs.map((c) => [c.cid, c.n]), [[7, 5], [8, 1]])
})

test("group map comes from the selected member with most photos", () => {
  const grp = (tag: string, who: number[], withMap = true) => [{ id: "g", name: "G", members: [], map: withMap ? gmap(tag, who) : null }]
  const h = household({ a: { groups: grp("fromA", [1]) }, b: { groups: grp("fromB", [2]) } })
  assert.equal(viewFor(h, [1, 2]).groups![0].map!.name, "fromA")
  assert.equal(viewFor(h, [2]).groups![0].map!.name, "fromB")
  // map photos must include a selected member
  assert.equal(viewFor(h, [1, 2]).groups![0].map!.photos.length, 1)
  const h2 = household({ a: { groups: grp("fromA", [1]) } })
  assert.equal(viewFor(h2, [2]).groups?.[0]?.map ?? null, null)
})

test("group member links to other decks are removed", () => {
  const m = { cid: 9, name: "Z", first: "Z", face: "", together: 3, url: "/other/", slug: "other" }
  const h = household({ a: { groups: [{ id: "g", name: "G", members: [m], map: null }] } })
  const out = viewFor(h, [1]).groups![0].members[0] as any
  assert.equal("url" in out, false)
  assert.equal("slug" in out, false)
  assert.equal(out.name, "Z")
})

test("counts come from the subset summary", () => {
  const h = household()
  const v = viewFor(h, [1, 2])
  assert.equal(v.n_photos, 140)
  assert.equal(v.n_events, 4)
  assert.equal(v.events[0].n, 20)
  assert.equal(viewFor(h, [2]).n_photos, 50)
  assert.equal(viewFor(h, [1]).hero, "hero1")
  assert.equal(viewFor(h, [2]).hero, "hero2")
  assert.equal(viewFor(h, [1, 2]).hero, "hero1")
})

test("couple picks pass through unchanged", () => {
  assert.deepEqual(viewFor(household(), [2]).picks, ["couple-pick"])
})

test("view carries no slug and no n_pool", () => {
  const h = household({ a: { n_pool: 99 } })
  const v = viewFor(h, [1, 2]) as any
  assert.equal("slug" in v, false)
  assert.equal(v.n_pool, undefined)
})

test("map photo of only an unselected member is dropped", () => {
  const grp = [{ id: "g", name: "G", members: [], map: { ...gmap("m", [1]), photos: [
    { id: "p1", s: "", l: "", gallery: "X", mem: [], who: [1] },
    { id: "p2", s: "", l: "", gallery: "X", mem: [], who: [2] },
  ] } }]
  const h = household({ a: { groups: grp } })
  assert.deepEqual(viewFor(h, [1]).groups![0].map!.photos.map((p) => p.id), ["p1"])
})

test("map photo with no who is dropped", () => {
  const grp = [{ id: "g", name: "G", members: [], map: { ...gmap("m", [1]), photos: [
    { id: "p1", s: "", l: "", gallery: "X", mem: [], who: [1] },
    { id: "p2", s: "", l: "", gallery: "X", mem: [] },
  ] } }]
  const h = household({ a: { groups: grp } })
  assert.deepEqual(viewFor(h, [1, 2]).groups![0].map!.photos.map((p) => p.id), ["p1"])
})

test("gallery shot with no who is hidden", () => {
  const noWho = { url: "n", thumbs: [], n_alt: 0, time: "9:00 AM", portrait: false }
  const g = [{ name: "Haldi", n_all: 2, shots: [noWho, shot("a", [1])] }]
  const h = household({ a: { gallery: g } })
  assert.deepEqual(viewFor(h, [1, 2]).gallery[0].shots.map((s) => s.url), ["a"])
})

const pe = (url: string, who?: number[], zone: "shown" | "skipped" | "below_bar" = "shown") =>
  ({ url, zone, rank: 0.5, ...(who ? { who } : {}) })

test("mergePools unions by url, shared photos first, drops unselected-only", () => {
  const pools = {
    1: [pe("a", [1]), pe("ab", [1, 2]), pe("ac", [1, 3])],
    2: [pe("b", [2]), pe("ab", [1, 2])],
    3: [pe("c", [3])],
  }
  assert.deepEqual(mergePools(pools, [1, 2]).map((e) => e.url), ["ab", "a", "ac", "b"])
  assert.deepEqual(mergePools(pools, [2]).map((e) => e.url), ["b", "ab"])
})

test("mergePools: entry without who belongs to its pool's member; best zone wins", () => {
  const pools = { 1: [pe("x", undefined, "below_bar")], 2: [pe("x", [1, 2], "shown")] }
  const out = mergePools(pools, [1, 2])
  assert.equal(out.length, 1)
  assert.equal(out[0].zone, "shown")
  assert.deepEqual([...out[0].who!].sort(), [1, 2])
})

test("hash sel round-trips and keeps the route", () => {
  assert.deepEqual(readHash("#/all?sel=1,2"), { route: "#/all", sel: [1, 2] })
  assert.deepEqual(readHash("#people"), { route: "#people", sel: null })
  assert.deepEqual(readHash("#?sel=x"), { route: "#", sel: null })
  assert.equal(writeHash("#/map?sel=1", [1, 2]), "#/map?sel=1,2")
  assert.equal(writeHash("", [5]), "#?sel=5")
  assert.deepEqual(cleanSel([9, 2, 2], [1, 2, 3]), [2])
  assert.deepEqual(cleanSel([9], [1, 2]), [1, 2])
})

test("readHash ignores malformed percent sequences instead of throwing", () => {
  assert.deepEqual(readHash("#?sel=%E0"), { route: "#", sel: null })
  assert.deepEqual(readHash("#/all?sel=%"), { route: "#/all", sel: null })
})

test("gallery order spans days: Friday shots before Saturday morning, members interleaved by time", () => {
  const evd = (name: string, day: string, first: string) => ({ ...ev(name, 1), day, first })
  const events = [evd("Sangeet", "Fri Apr 24", "6:24 PM"), evd("Wedding", "Sat Apr 25", "8:22 AM")]
  const at = (url: string, who: number[], time: string, event: string) => ({ ...shot(url, who, time), event })
  // each member's list is chronological; one bucket spans Friday evening and Saturday morning
  const ga = [{ name: "You in focus", n_all: 2, shots: [at("a-fri", [1], "8:00 PM", "Sangeet"), at("a-sat", [1], "9:00 AM", "Wedding")] }]
  const gb = [{ name: "You in focus", n_all: 2, shots: [at("b-fri", [2], "7:00 PM", "Sangeet"), at("b-sat", [2], "10:00 AM", "Wedding")] }]
  const h = household({ a: { gallery: ga, events }, b: { gallery: gb, events } })
  assert.deepEqual(viewFor(h, [1]).gallery[0].shots.map((s) => s.url), ["a-fri", "a-sat"])
  assert.deepEqual(viewFor(h, [1, 2]).gallery[0].shots.map((s) => s.url), ["b-fri", "a-fri", "a-sat", "b-sat"])
})
