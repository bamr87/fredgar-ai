"""Website and reference discovery.

The domain is the linchpin of the whole framework. Once a company's own site is
known and *verified*, almost every other attribute becomes reachable from public
sources: legal name, address, phone, sector language, leadership, careers pages
as a size proxy, and `sameAs` links out to every other public reference.

So this module is deliberately conservative. An unverified domain is worse than
no domain, because everything downstream inherits the error silently. Every
candidate must survive a verification step before it is allowed to be a
`website` rather than a `website_candidate`.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from html.parser import HTMLParser

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost
from ..normalize import clean

# Aggregators and profile sites. These are excellent *references* and terrible
# *websites* - mistaking one for the company's own domain poisons everything.
AGGREGATORS = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "crunchbase.com",
    "bloomberg.com",
    "reuters.com",
    "zoominfo.com",
    "dnb.com",
    "dunsregistered.com",
    "glassdoor.com",
    "indeed.com",
    "wikipedia.org",
    "wikidata.org",
    "opencorporates.com",
    "yellowpages.com",
    "yelp.com",
    "manta.com",
    "bizapedia.com",
    "companieshouse.gov.uk",
    "sec.gov",
    "gleif.org",
    "panjiva.com",
    "importgenius.com",
    "alibaba.com",
    "made-in-china.com",
    "europages.com",
    "kompass.com",
    "thomasnet.com",
    "tradeindia.com",
    "indiamart.com",
}

# Signals that a domain resolves but hosts nothing real.
PARKED_MARKERS = re.compile(
    r"(domain (is )?for sale|buy this domain|parked (free )?(by|at)|"
    r"under construction|coming soon|godaddy\.com/forsale|sedoparking|"
    r"this domain may be for sale|default web site page|apache2 (ubuntu|debian) default)",
    re.I,
)

# First tokens that name a place rather than a company. Kept small and explicit;
# the country list in the adapter covers the rest.
_GEO_STEMS = {
    "shanghai",
    "beijing",
    "shenzhen",
    "guangzhou",
    "tianjin",
    "zhejiang",
    "jiangsu",
    "guangdong",
    "shandong",
    "hebei",
    "henan",
    "anhui",
    "fujian",
    "sichuan",
    "hunan",
    "hubei",
    "ningbo",
    "suzhou",
    "qingdao",
    "dalian",
    "wuxi",
    "foshan",
    "dongguan",
    "chongqing",
    "chengdu",
    "wuhan",
    "xian",
    "nanjing",
    "hangzhou",
    "shenyang",
    "changchun",
    "taiwan",
    "tokyo",
    "osaka",
    "seoul",
    "mumbai",
    "delhi",
    "chennai",
    "jakarta",
    "bangkok",
    "manila",
    "istanbul",
    "moscow",
    "warsaw",
    "berlin",
    "munich",
    "hamburg",
    "paris",
    "milano",
    "madrid",
    "london",
    "dublin",
    "vienna",
    "zurich",
    "monterrey",
    "toronto",
    "detroit",
    "chicago",
    "houston",
    "atlanta",
    "boston",
    "cairo",
    "america",
    "american",
    "europe",
    "european",
    "asia",
    "asian",
    "national",
    "global",
    "international",
    "united",
    "general",
    "standard",
    "universal",
    "custom",
    "premier",
    "quality",
    "advanced",
    "modern",
    "superior",
}

GENERIC_TLD = [".com", ".net", ".co", ".io"]
COUNTRY_TLD = {
    "US": [".com", ".us"],
    "GB": [".co.uk", ".com", ".uk"],
    "DE": [".de", ".com"],
    "FR": [".fr", ".com"],
    "IT": [".it", ".com"],
    "ES": [".es", ".com"],
    "NL": [".nl", ".com"],
    "BE": [".be", ".com"],
    "SE": [".se", ".com"],
    "NO": [".no"],
    "DK": [".dk"],
    "FI": [".fi"],
    "PL": [".pl", ".com"],
    "CZ": [".cz"],
    "AT": [".at"],
    "CH": [".ch"],
    "IE": [".ie", ".com"],
    "CN": [".com.cn", ".cn", ".com"],
    "JP": [".co.jp", ".jp"],
    "KR": [".co.kr", ".kr"],
    "IN": [".co.in", ".in", ".com"],
    "ID": [".co.id", ".id"],
    "MY": [".com.my"],
    "SG": [".com.sg", ".sg"],
    "TH": [".co.th"],
    "VN": [".com.vn", ".vn"],
    "AU": [".com.au"],
    "NZ": [".co.nz"],
    "CA": [".ca", ".com"],
    "MX": [".com.mx", ".mx"],
    "BR": [".com.br"],
    "AR": [".com.ar"],
    "TR": [".com.tr"],
    "ZA": [".co.za"],
}


# ============================================================ HTML parsing ===
class _Extract(HTMLParser):
    """Pull the few things that actually identify a site. Stdlib only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta, self.jsonld, self.links = "", {}, [], []
        self._in_title = self._in_ld = False
        self._ld_buf = []
        self.text_chunks = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag in ("script", "style"):
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._in_ld = True
                self._ld_buf = []
            else:
                self._skip += 1
        elif tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k and a.get("content"):
                self.meta.setdefault(k, a["content"].strip())
        elif tag == "link" and (a.get("rel") or "") and a.get("href"):
            rel = " ".join(a["rel"]) if isinstance(a["rel"], list) else str(a["rel"])
            if "canonical" in rel.lower():
                self.meta.setdefault("canonical", a["href"].strip())
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._in_ld:
                self._in_ld = False
                raw = "".join(self._ld_buf).strip()
                try:
                    self.jsonld.append(json.loads(raw))
                except Exception:
                    pass
            elif self._skip:
                self._skip -= 1
        elif tag == "style" and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self._ld_buf.append(data)
        elif not self._skip:
            d = data.strip()
            if d:
                self.text_chunks.append(d)

    @property
    def text(self) -> str:
        return " ".join(self.text_chunks)[:20000]


def _iter_jsonld_orgs(blobs):
    """schema.org lets Organization hide in @graph, arrays, or nested nodes."""
    ORG = {
        "organization",
        "corporation",
        "localbusiness",
        "manufacturer",
        "company",
        "ngo",
        "educationalorganization",
    }
    stack = list(blobs)
    seen = 0
    while stack and seen < 500:
        seen += 1
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        if "@graph" in node:
            stack.append(node["@graph"])
        t = node.get("@type")
        types = [t] if isinstance(t, str) else (t or [])
        if any(str(x).lower() in ORG for x in types):
            yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                stack.append(v)


def parse_page(html_text: str) -> dict:
    """Everything identifying we can get from one HTML document."""
    p = _Extract()
    try:
        p.feed(html_text)
    except Exception:
        pass
    orgs = list(_iter_jsonld_orgs(p.jsonld))
    org = orgs[0] if orgs else {}

    def _flat(v):
        if isinstance(v, dict):
            return v.get("name") or v.get("@id") or None
        if isinstance(v, list):
            return [x for x in (_flat(i) for i in v) if x]
        return v

    addr = org.get("address") or {}
    if isinstance(addr, list):
        addr = addr[0] if addr else {}
    return {
        "title": html.unescape(p.title).strip(),
        "meta": p.meta,
        "description": p.meta.get("og:description") or p.meta.get("description"),
        "site_name": p.meta.get("og:site_name"),
        "canonical": p.meta.get("canonical") or p.meta.get("og:url"),
        "org_name": org.get("name"),
        "org_legal_name": org.get("legalName"),
        "org_same_as": [x for x in (org.get("sameAs") or []) if isinstance(x, str)],
        "org_phone": _flat(org.get("telephone")),
        "org_email": _flat(org.get("email")),
        "org_founded": org.get("foundingDate"),
        "org_employees": (org.get("numberOfEmployees") or {}).get("value")
        if isinstance(org.get("numberOfEmployees"), dict)
        else org.get("numberOfEmployees"),
        "org_country": (addr or {}).get("addressCountry") if isinstance(addr, dict) else None,
        "org_locality": (addr or {}).get("addressLocality") if isinstance(addr, dict) else None,
        "org_street": (addr or {}).get("streetAddress") if isinstance(addr, dict) else None,
        "org_vat": org.get("vatID") or org.get("taxID"),
        "links": p.links,
        "text": p.text,
        "has_jsonld_org": bool(orgs),
    }


def registrable_domain(url: str) -> str:
    host = urllib.parse.urlsplit(url if "//" in url else "//" + url).hostname or ""
    host = host.lower().lstrip("www.")
    parts = host.split(".")
    # Good enough without a PSL dependency: treat 2-part public suffixes explicitly.
    if len(parts) >= 3 and ".".join(parts[-2:]) in {
        "co.uk",
        "com.cn",
        "co.jp",
        "com.au",
        "co.nz",
        "com.br",
        "com.mx",
        "co.za",
        "co.kr",
        "co.in",
        "com.tr",
        "com.sg",
        "com.my",
        "co.th",
        "com.vn",
        "co.id",
        "com.ar",
        "org.uk",
        "ltd.uk",
    }:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_aggregator(url: str) -> bool:
    d = registrable_domain(url)
    return any(d == a or d.endswith("." + a) for a in AGGREGATORS)


# ------------------------------------------------------------- name agreement --
# Generic words that describe a company without distinguishing it from another.
# Extra tokens drawn only from this set are noise; anything else is a different
# entity until proven otherwise.
DESCRIPTORS = {
    "technologies",
    "technology",
    "solutions",
    "systems",
    "industries",
    "industrial",
    "international",
    "global",
    "worldwide",
    "group",
    "holdings",
    "holding",
    "company",
    "enterprises",
    "products",
    "services",
    "manufacturing",
    "engineering",
    "components",
    "equipment",
    "supply",
    "trading",
    "works",
    "north",
    "south",
    "east",
    "west",
    "america",
    "americas",
    "europe",
    "asia",
    "pacific",
    "emea",
    "apac",
    "usa",
    "us",
    "uk",
    "inc",
    "co",
}


def name_agreement(want: str, candidate: str) -> tuple[float, str]:
    """How strongly does `candidate` name the same entity as `want`?

    Directional, not symmetric-by-accident. The failure this exists to prevent:
    a naive prefix test matches "Eaton" against "Eaton Vance Corp", a completely
    unrelated company, and every downstream attribute inherits that error.

    The rule: essentially all of the company's own tokens must be present, AND
    any extra tokens the candidate brings must be generic descriptors. A single
    distinctive extra token ("vance") means a different entity.
    """
    A = set(clean(want).split())
    B = set(clean(candidate).split())
    if not A or not B:
        return 0.0, "empty"
    inter = A & B
    if not inter:
        return 0.0, "no_overlap"

    # Coverage is measured over DISTINCTIVE tokens only. List names carry legal
    # detail that brand sites drop - "Liebherr-International SA" against a site
    # calling itself "Liebherr Group" is the same company, and counting
    # "international" as a missing token rejected it. Descriptors are noise on
    # BOTH sides or neither.
    dist_A = {t for t in A if t not in DESCRIPTORS} or A
    cov_want = len(dist_A & B) / len(dist_A)
    extra = B - A
    distinctive_extra = {t for t in extra if t not in DESCRIPTORS and len(t) > 2}

    if cov_want < 0.8:
        return round(cov_want * 0.5, 3), f"partial_cov={cov_want:.2f}"
    if distinctive_extra:
        # Different entity in the same family, or a different entity entirely.
        return 0.25, f"distinctive_extra={sorted(distinctive_extra)[:3]}"
    return round(0.6 + 0.4 * (len(inter) / len(B)), 3), f"cov={cov_want:.2f}"


def title_agreement(want: str, title: str) -> tuple[float, str]:
    """Titles carry taglines ("Gibbens Industries - Automotive Components"), so
    extra tokens are expected and must not be penalised. We instead demand that
    EVERY token of the company name appears. Single-token names are refused
    outright here - "Eaton" appears in the title of several unrelated firms and
    a title alone must never be enough to carry one."""
    A = [t for t in clean(want).split()]
    if len(A) < 2:
        return 0.0, "single_token_title_unsafe"
    T = set(clean(title).split()) | set(_fold_title(title).split())
    hit = sum(1 for t in A if t in T)
    cov = hit / len(A)
    return (round(cov, 3), f"title_cov={cov:.2f}") if cov >= 0.99 else (0.0, f"title_cov={cov:.2f}")


def _fold_title(t: str) -> str:
    """Titles often use separators the cleaner drops; keep raw tokens too."""
    import re as _re

    return _re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


# ------------------------------------------------------------- verification --
def verify_site(company_name: str, url: str, page: dict) -> tuple[bool, float, str]:
    """Does this page belong to this company? (verified, confidence, why)

    Scored on independent signals rather than one string match, because any
    single signal is defeatable: a title can be a slogan, a JSON-LD block can be
    a template default, a domain can merely resemble the name.
    """
    if PARKED_MARKERS.search(page.get("text", "")[:3000]) or PARKED_MARKERS.search(
        page.get("title", "")
    ):
        return False, 0.0, "parked_or_placeholder"
    if is_aggregator(url):
        return False, 0.0, "aggregator_not_own_site"

    want = clean(company_name)
    if not want:
        return False, 0.0, "unusable_name"

    score, why = 0.0, []
    contradicted = False
    for label, value, weight in (
        ("jsonld_legal_name", page.get("org_legal_name"), 0.45),
        ("jsonld_name", page.get("org_name"), 0.40),
        ("og_site_name", page.get("site_name"), 0.30),
        ("title", page.get("title"), 0.25),
    ):
        if not value:
            continue
        if label == "title":
            agree, note = title_agreement(want, str(value))
        else:
            agree, note = name_agreement(want, str(value))
        if agree >= 0.6:
            score += weight
            why.append(f"{label}~{agree:.2f}")
        elif label in ("jsonld_legal_name", "jsonld_name", "og_site_name") and note.startswith(
            "distinctive_extra"
        ):
            # The site states its own identity and it is not ours. That is a
            # positive disqualification, not merely a missing signal.
            contradicted = True
            why.append(f"{label}_CONTRADICTS:{note}")

    if contradicted:
        return False, 0.0, ",".join(why)

    # The domain echoing the name is corroboration, never proof on its own.
    dom = registrable_domain(url).split(".")[0]
    joined = want.replace(" ", "")
    if dom and (dom == joined or joined.startswith(dom) or dom.startswith(joined[:8])):
        score += 0.20
        why.append("domain_echo")

    # The name appearing in body copy (copyright lines, "About <Name>").
    if want and want in clean(page.get("text", ""))[:8000]:
        score += 0.15
        why.append("body_mention")

    conf = min(0.99, round(score, 3))

    # A one-token company name ("Eaton", "Genzyme") is inherently ambiguous -
    # it will honestly match several unrelated firms. Demand an exact domain
    # echo before trusting it, rather than pretending the score means more.
    if len(want.split()) == 1:
        dom0 = registrable_domain(url).split(".")[0]
        if dom0 != want.replace(" ", ""):
            return False, min(conf, 0.5), ",".join(why) + ",single_token_needs_exact_domain"

    return (conf >= 0.55), conf, ",".join(why) or "no_signal"


# ================================================================ providers ==
class DomainCandidates(BaseProvider):
    """Cheap, offline guesses. Costs nothing, resolves a large share of the list."""

    name = "domain_guess"
    requires = frozenset({"name"})
    provides = frozenset({"website_candidate"})
    cost = Cost.FREE

    def run(self, rec, ctx):
        base = clean(rec.get("name"))
        if not base:
            return
        toks = base.split()
        stems = {"".join(toks), "".join(toks[:2])}
        # A bare first token is only a usable stem when it is DISTINCTIVE.
        # Measured against the live web, generic and geographic first tokens
        # produced confident guesses at entirely unrelated companies:
        # "Custom Mold & Design" -> custom.com, "Zhejiang Yinzuo" -> zhejiang.cn,
        # "Integral Access Inc." -> integral.com (an unrelated FX company).
        if len(toks) == 1 or (
            toks[0] not in DESCRIPTORS and toks[0] not in _GEO_STEMS and len(toks[0]) >= 5
        ):
            stems.add(toks[0])
        stems = {s for s in stems if len(s) >= 3}
        tlds = COUNTRY_TLD.get((rec.get("country_iso") or "").upper(), GENERIC_TLD)
        seen = set()
        for s in sorted(stems, key=len, reverse=True):
            for t in tlds[:3]:
                url = f"https://{s}{t}"
                if url in seen:
                    continue
                seen.add(url)
                # Deliberately low: this is a hypothesis for SiteProbe to test.
                yield Claim(
                    "website_candidate", url, 0.25, self.name, Evidence(locator=f"heuristic:{s}{t}")
                )


class SearchDiscovery(BaseProvider):
    """Ask a search backend when guessing produced nothing verifiable.

    The backend is injected (ctx.shared['search']) so you can point this at
    SearXNG, Brave, DuckDuckGo HTML or an internal index without touching the
    framework. Signature: search(query:str, n:int) -> [{'url','title','snippet'}]
    """

    name = "web_search"
    requires = frozenset({"name"})
    provides = frozenset({"website_candidate", "reference"})
    cost = Cost.SEARCH
    rate_per_sec = 0.5

    def eligible(self, rec):
        if not self.requires <= rec.available():
            return False
        # Only pay for search if no candidate has been verified yet.
        return not any(c.verified for c in rec.claims_for("website"))

    def run(self, rec, ctx):
        backend = (ctx.shared or {}).get("search")
        if backend is None:
            return
        q = rec.get("name")
        if rec.get("country"):
            q = f"{q} {rec.get('country')}"
        for r in backend(f"{q} official site", 8) or []:
            url, title = r.get("url", ""), r.get("title", "")
            if not url:
                continue
            ev = Evidence(
                url=url, snippet=(r.get("snippet") or title)[:400], locator="search_result"
            )
            if is_aggregator(url):
                # Not the company's site, but exactly the kind of public
                # reference the master record should carry.
                yield Claim(
                    "reference",
                    {"url": url, "title": title, "kind": registrable_domain(url)},
                    0.5,
                    self.name,
                    ev,
                )
            else:
                yield Claim("website_candidate", url, 0.45, self.name, ev)


class SiteProbe(BaseProvider):
    """Fetch candidates, verify one, and harvest what the page asserts."""

    name = "site_probe"
    requires = frozenset({"website_candidate"})
    provides = frozenset(
        {
            "website",
            "legal_name",
            "description",
            "sameAs",
            "phone",
            "hq_city",
            "hq_country_site",
            "founded",
            "employees_site",
        }
    )
    cost = Cost.FETCH
    rate_per_sec = 3.0
    max_candidates = 4

    def run(self, rec, ctx):
        http = ctx.http
        if http is None:
            return
        cands = [c for c in rec.claims_for("website_candidate")]
        cands.sort(key=lambda c: c.confidence, reverse=True)
        tried = set()
        best = None

        for c in cands[: self.max_candidates]:
            url = c.value if isinstance(c.value, str) else None
            if not url or registrable_domain(url) in tried:
                continue
            tried.add(registrable_domain(url))
            try:
                body = http.get(url, accept="text/html").decode("utf-8", "replace")
            except Exception:
                continue
            page = parse_page(body)
            ok, conf, why = verify_site(rec.get("name"), url, page)
            if ok and (best is None or conf > best[1]):
                best = (url, conf, why, page)
            if best and best[1] >= 0.85:
                break

        if not best:
            return
        url, conf, why, page = best
        final = page.get("canonical") or url
        ev = Evidence(url=url, snippet=(page.get("title") or "")[:300], locator=f"verify:{why}")
        yield Claim("website", final, conf, self.name, ev, verified=True)

        for fld, val, cf in (
            ("legal_name", page.get("org_legal_name") or page.get("org_name"), 0.85),
            ("description", page.get("description"), 0.75),
            ("phone", page.get("org_phone"), 0.8),
            ("hq_city", page.get("org_locality"), 0.75),
            ("hq_country_site", page.get("org_country"), 0.75),
            ("founded", (page.get("org_founded") or "")[:4] or None, 0.8),
            ("employees_site", page.get("org_employees"), 0.7),
        ):
            if val:
                yield Claim(
                    fld, val, cf, "site_jsonld" if page["has_jsonld_org"] else self.name, ev
                )

        # sameAs is the single richest reference source a site can hand you.
        for s in page.get("org_same_as", [])[:12]:
            yield Claim(
                "reference",
                {"url": s, "title": None, "kind": registrable_domain(s)},
                0.9,
                "site_jsonld",
                Evidence(url=final, locator="jsonld:sameAs"),
            )
